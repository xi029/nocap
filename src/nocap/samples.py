"""Original fictional documents, freely reusable under this project's license."""

DOCUMENTS = {
    "refund-policy.md": """# Northstar refund policy

Customers can request a refund within 30 days of purchase. To request a refund, email support@northstar.example with your order ID. Refunds go to the original payment method within 5 business days.

Annual subscriptions are eligible for a refund within 30 days of the initial purchase. Renewals are non-refundable. This policy applies to purchases on or after September 1, 2026.""",
    "deployment.md": """# Northstar deployment guide

Northstar supports Docker Compose for self-hosted deployment. The service listens on port 8080. Persist the /app/data directory using a Docker volume. A minimum of 4 GB RAM is required.

The default database is SQLite. Back up the database before upgrading. Use the health endpoint at /health to check service readiness. Kubernetes deployment is not documented in this guide.""",
    "privacy.md": """# Northstar privacy notes

Self-hosted Northstar stores documents on your own server. By default, telemetry is disabled. Uploaded documents are not sent to an external service unless you configure a hosted model provider.

Delete a document from the workspace to remove it from future retrieval. Existing query records retain their evidence excerpts until you remove the local database. Encryption at rest is not included.""",
    "support.md": """# Northstar support

Support is available by email at support@northstar.example, Monday through Friday. Include your version number and a short description of the problem. Enterprise support response times depend on the contract.

Northstar offers a free community plan and a paid team plan. Exact plan pricing is not listed in this document. Contact sales for a current quote.""",
    "中文说明.md": """# Northstar 本地部署

Northstar 支持使用 Docker Compose 本地部署。服务默认端口是 8080，最低需要 4 GB 内存。请使用持久化卷保存 /app/data 目录。

默认关闭遥测。自行托管时，上传的文档保存在自己的服务器上。只有配置托管模型服务后，证据片段才会发送到外部服务。""",
}
CONFLICT_DOCUMENT = (
    "refund-policy-draft.md",
    "# Draft refund policy — unresolved source conflict\n\n"
    "Customers can request a refund within 14 days of purchase. To request a refund, email "
    "support@northstar.example with your order ID. Refunds go to the original payment method "
    "within 5 business days.\n\nThis draft conflicts with the published refund policy. "
    "It is included for the conflict demo; no precedence is assigned automatically.",
)
SCENARIOS = [
    {"label": "Supported", "question": "How do I request a refund?"},
    {"label": "Missing detail", "question": "What is the exact team plan pricing?"},
    {"label": "No evidence", "question": "Who won the lunar chess championship?"},
    {"label": "中文", "question": "本地部署默认端口是多少？"},
]
