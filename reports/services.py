"""Read-only business reporting calculations."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import (
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from customers.models import Customer
from inventory.models import StockMovement
from invoices.models import Invoice
from products.models import Product
from sales.models import Sale, SaleItem


PERIOD_CHOICES = (
    ("today", "Today"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
)
MONEY_FIELD = DecimalField(max_digits=24, decimal_places=2)
ZERO_MONEY = Value(Decimal("0.00"), output_field=MONEY_FIELD)


@dataclass(frozen=True)
class ReportPeriod:
    key: str
    label: str
    start_date: date
    end_date: date
    start_at: datetime
    end_at: datetime

    @property
    def day_count(self):
        return (self.end_date - self.start_date).days + 1


def resolve_period(value, *, today=None):
    """Resolve an allowlisted local-calendar reporting period."""
    labels = dict(PERIOD_CHOICES)
    key = value if value in labels else "30d"
    local_today = today or timezone.localdate()
    days = {"today": 1, "7d": 7, "30d": 30}[key]
    start_date = local_today - timedelta(days=days - 1)
    end_date = local_today
    current_timezone = timezone.get_current_timezone()
    start_at = timezone.make_aware(
        datetime.combine(start_date, time.min),
        current_timezone,
    )
    end_at = timezone.make_aware(
        datetime.combine(end_date + timedelta(days=1), time.min),
        current_timezone,
    )
    return ReportPeriod(
        key=key,
        label=labels[key],
        start_date=start_date,
        end_date=end_date,
        start_at=start_at,
        end_at=end_at,
    )


def _sales_in_period(period):
    """Completed Sales in the period, excluding any that were voided.

    A voided Sale keeps its record but its goods went back and its money was
    returned, so counting it would overstate takings and gross profit.
    """
    return Sale.objects.filter(
        created_at__gte=period.start_at,
        created_at__lt=period.end_at,
        reversal__isnull=True,
    )


def _sale_items_in_period(period):
    return SaleItem.objects.filter(
        sale__created_at__gte=period.start_at,
        sale__created_at__lt=period.end_at,
        sale__reversal__isnull=True,
    )


def _daily_revenue(period):
    rows = (
        _sales_in_period(period)
        .annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(revenue=Coalesce(Sum("net_amount"), ZERO_MONEY))
        .order_by("day")
    )
    by_date = {row["day"]: row["revenue"] for row in rows}
    return [
        {
            "date": period.start_date + timedelta(days=offset),
            "revenue": by_date.get(
                period.start_date + timedelta(days=offset),
                Decimal("0.00"),
            ),
        }
        for offset in range(period.day_count)
    ]


def _sales_summary(period):
    return _sales_in_period(period).aggregate(
        revenue=Coalesce(Sum("net_amount"), ZERO_MONEY),
        sale_count=Count("pk"),
        average_sale=Coalesce(Avg("net_amount"), ZERO_MONEY),
        tax_collected=Coalesce(Sum("tax_amount"), ZERO_MONEY),
        invoiced_sales=Count("pk", filter=Q(invoice__isnull=False)),
        walk_in_count=Count("pk", filter=Q(customer__isnull=True)),
    )


def _margin_metrics(item_queryset):
    """Gross margin over the SaleItems that carry a cost snapshot.

    SaleItems recorded before cost capture existed have no unit_cost, so they
    are excluded from cost and profit and reported separately as uncosted
    rather than being guessed from the Product's current cost_price.
    """
    costed = item_queryset.filter(unit_cost__isnull=False)
    totals = costed.aggregate(
        cost=Coalesce(Sum("cost_subtotal"), ZERO_MONEY),
        costed_revenue=Coalesce(Sum("subtotal"), ZERO_MONEY),
        costed_items=Count("pk"),
    )
    uncosted_items = item_queryset.filter(unit_cost__isnull=True).count()
    gross_profit = totals["costed_revenue"] - totals["cost"]
    margin_rate = None
    if totals["costed_revenue"]:
        margin_rate = (
            gross_profit * Decimal("100.00") / totals["costed_revenue"]
        ).quantize(Decimal("0.01"))
    return {
        "cost": totals["cost"],
        "costed_revenue": totals["costed_revenue"],
        "gross_profit": gross_profit,
        "margin_rate": margin_rate,
        "costed_items": totals["costed_items"],
        "uncosted_items": uncosted_items,
        "cost_is_complete": uncosted_items == 0,
    }


def get_sales_report(period):
    """Return selected-period Sales metrics from immutable Sale data."""
    summary = _sales_summary(period)
    item_queryset = _sale_items_in_period(period)
    top_base = item_queryset.values(
        "product_id",
        "product__sku",
        "product__name",
    ).annotate(
        quantity=Sum("quantity"),
        revenue=Coalesce(Sum("subtotal"), ZERO_MONEY),
    )
    return {
        **summary,
        "margin": _margin_metrics(item_queryset),
        "daily_revenue": _daily_revenue(period),
        "top_products_by_revenue": list(
            top_base.order_by("-revenue", "product_id")[:5]
        ),
        "top_products_by_quantity": list(
            top_base.order_by("-quantity", "product_id")[:5]
        ),
        "recent_sales": list(
            _sales_in_period(period)
            .select_related("customer", "created_by", "invoice")
            .order_by("-created_at", "-pk")[:10]
        ),
    }


def _inventory_health():
    return Product.objects.filter(is_active=True).aggregate(
        active_products=Count("pk"),
        low_stock=Count(
            "pk",
            filter=Q(current_stock__gt=0)
            & Q(current_stock__lte=F("low_stock_threshold")),
        ),
        out_of_stock=Count("pk", filter=Q(current_stock=0)),
    )


def _inventory_movements(period, user):
    queryset = StockMovement.objects.filter(
        created_at__gte=period.start_at,
        created_at__lt=period.end_at,
    )
    if not user.is_superuser:
        queryset = queryset.filter(product__is_active=True)
    return queryset


def get_inventory_report(period, user):
    """Return current stock health and selected-period movement metrics."""
    movements = _inventory_movements(period, user)
    adjustment_delta = ExpressionWrapper(
        F("new_stock") - F("previous_stock"),
        output_field=IntegerField(),
    )
    movement_metrics = movements.aggregate(
        stock_in_units=Coalesce(
            Sum("quantity", filter=Q(movement_type=StockMovement.MovementType.STOCK_IN)),
            0,
        ),
        stock_out_units=Coalesce(
            Sum("quantity", filter=Q(movement_type=StockMovement.MovementType.STOCK_OUT)),
            0,
        ),
        adjustment_count=Count(
            "pk", filter=Q(movement_type=StockMovement.MovementType.ADJUSTMENT)
        ),
        adjustment_activity=Coalesce(
            Sum("quantity", filter=Q(movement_type=StockMovement.MovementType.ADJUSTMENT)),
            0,
        ),
        net_adjustment=Coalesce(
            Sum(
                adjustment_delta,
                filter=Q(movement_type=StockMovement.MovementType.ADJUSTMENT),
            ),
            0,
        ),
    )
    return {
        **_inventory_health(),
        **movement_metrics,
        "recent_movements": list(
            movements.select_related("product", "performed_by")
            .order_by("-created_at", "-pk")[:10]
        ),
    }


def get_customer_metrics(period):
    """Return current active-Customer and selected-period activity counts."""
    active_customers = Customer.objects.filter(is_active=True)
    counts = active_customers.aggregate(
        active_count=Count("pk", distinct=True),
        created_in_period=Count(
            "pk",
            filter=Q(created_at__gte=period.start_at, created_at__lt=period.end_at),
            distinct=True,
        ),
        with_sales_in_period=Count(
            "pk",
            filter=Q(
                sales__created_at__gte=period.start_at,
                sales__created_at__lt=period.end_at,
            ),
            distinct=True,
        ),
    )
    counts["walk_in_sales"] = _sales_in_period(period).filter(
        customer__isnull=True
    ).count()
    return counts


def get_invoice_metrics(period):
    """Return document issuance volume and Sale-based issuance coverage."""
    issued = Invoice.objects.filter(
        issued_at__gte=period.start_at,
        issued_at__lt=period.end_at,
    )
    sale_counts = _sales_in_period(period).aggregate(
        eligible_sales=Count("pk"),
        invoiced_sales=Count("pk", filter=Q(invoice__isnull=False)),
    )
    eligible_sales = sale_counts["eligible_sales"]
    issuance_rate = None
    if eligible_sales:
        issuance_rate = (
            Decimal(sale_counts["invoiced_sales"]) * Decimal("100.00")
            / Decimal(eligible_sales)
        ).quantize(Decimal("0.01"))
    return {
        "issued_count": issued.count(),
        **sale_counts,
        "issuance_rate": issuance_rate,
        "recent_invoices": list(
            issued.select_related("sale", "issued_by")
            .order_by("-issued_at", "-pk")[:10]
        ),
    }


def get_dashboard_data(period, user):
    """Return the focused KPI and attention data used by the root dashboard."""
    sales = _sales_summary(period)
    invoice_rate = None
    if sales["sale_count"]:
        invoice_rate = (
            Decimal(sales["invoiced_sales"]) * Decimal("100.00")
            / Decimal(sales["sale_count"])
        ).quantize(Decimal("0.01"))
    attention_products = list(
        Product.objects.filter(is_active=True)
        .filter(
            Q(current_stock=0)
            | Q(current_stock__gt=0, current_stock__lte=F("low_stock_threshold"))
        )
        .order_by("current_stock", "name", "pk")[:10]
    )
    return {
        "period": period,
        "revenue": sales["revenue"],
        "sale_count": sales["sale_count"],
        "average_sale": sales["average_sale"],
        "invoice_rate": invoice_rate,
        "margin": _margin_metrics(_sale_items_in_period(period)),
        "active_customers": Customer.objects.filter(is_active=True).count(),
        "inventory": _inventory_health(),
        "attention_products": attention_products,
        "recent_sales": list(
            _sales_in_period(period)
            .select_related("customer", "created_by", "invoice")
            .order_by("-created_at", "-pk")[:10]
        ),
        "daily_revenue": _daily_revenue(period),
    }
