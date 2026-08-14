from django.db import migrations


OPENING_BALANCE_REASON = "Opening balance migrated from Phase 3"


def create_opening_balances(apps, schema_editor):
    product_model = apps.get_model("products", "Product")
    movement_model = apps.get_model("inventory", "StockMovement")
    database_alias = schema_editor.connection.alias

    batch = []
    products = (
        product_model.objects.using(database_alias)
        .filter(current_stock__gt=0)
        .values_list("pk", "current_stock")
        .iterator(chunk_size=1000)
    )
    for product_id, current_stock in products:
        batch.append(
            movement_model(
                product_id=product_id,
                movement_type="ADJUSTMENT",
                quantity=current_stock,
                previous_stock=0,
                new_stock=current_stock,
                reason=OPENING_BALANCE_REASON,
                performed_by_id=None,
            )
        )
        if len(batch) == 1000:
            movement_model.objects.using(database_alias).bulk_create(batch)
            batch.clear()
    if batch:
        movement_model.objects.using(database_alias).bulk_create(batch)


def remove_opening_balances(apps, schema_editor):
    movement_model = apps.get_model("inventory", "StockMovement")
    movement_model.objects.using(schema_editor.connection.alias).filter(
        movement_type="ADJUSTMENT",
        previous_stock=0,
        performed_by_id=None,
        reason=OPENING_BALANCE_REASON,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_opening_balances, remove_opening_balances),
    ]
