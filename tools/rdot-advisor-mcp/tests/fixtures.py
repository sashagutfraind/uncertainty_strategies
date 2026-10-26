"""Sample enterprise-software architectures for the test harness, each with a stated goal."""

FIXTURES = [
    {
        "name": "payments_microservices",
        "description": (
            "A payments-processing system built as microservices: an API gateway, a payment-authorization "
            "service, a ledger service, and a notifications service, each with its own database, communicating "
            "over internal HTTP and a message queue. Card numbers pass through the authorization service before "
            "being tokenized."
        ),
        "goal": "reduce the risk of a data breach exposing card numbers or other sensitive payment data",
    },
    {
        "name": "healthcare_data_pipeline",
        "description": (
            "A batch data pipeline that ingests patient records nightly from several hospital systems, "
            "transforms them through a series of ETL jobs, and loads the results into a shared analytics "
            "warehouse used by researchers. Any single ETL job failing currently blocks the rest of the nightly "
            "run from completing."
        ),
        "goal": "improve resilience to partial outages so a single failing job doesn't block the whole pipeline",
    },
    {
        "name": "internal_admin_tool",
        "description": (
            "An internal admin dashboard used by support staff to look up and edit customer accounts directly "
            "in the production database. Any logged-in support staff member can query or modify any customer's "
            "record, and the tool uses a single shared service-account database credential."
        ),
        "goal": "reduce the risk of an insider incident or a compromised support-staff credential causing broad damage",
    },
]
