(() => {
    "use strict";

    if (typeof Chart === "undefined") {
        return;
    }

    const readPayload = (id) => {
        const element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    };

    const revenueCanvas = document.querySelector('[data-report-chart="revenue"]');
    const revenue = readPayload("dashboard-revenue-data");
    if (revenueCanvas && revenue) {
        new Chart(revenueCanvas, {
            type: "line",
            data: {
                labels: revenue.labels,
                datasets: [{
                    label: "Sales revenue (MYR)",
                    data: revenue.values,
                    borderColor: "#116466",
                    backgroundColor: "rgba(17, 100, 102, 0.12)",
                    fill: true,
                    tension: 0.25,
                    pointRadius: revenue.values.length > 14 ? 0 : 3,
                }],
            },
            options: {
                animation: false,
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } },
            },
        });
    }

    const productCanvas = document.querySelector('[data-report-chart="top-products"]');
    const products = readPayload("reports-top-products-data");
    if (productCanvas && products) {
        new Chart(productCanvas, {
            type: "bar",
            data: {
                labels: products.labels,
                datasets: [{
                    label: "Sales revenue (MYR)",
                    data: products.values,
                    backgroundColor: "#315f8c",
                    borderRadius: 4,
                }],
            },
            options: {
                animation: false,
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true } },
            },
        });
    }
})();
