# Buildable application image; production reference is systemd on Linux.
# Review and refresh the pinned image digest during dependency maintenance.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp FASTMCP_ENABLE_RICH_LOGGING=false
WORKDIR /opt/homelab-mcp
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && pip check
COPY app ./app
USER 1000:1000
# Binds loopback. Do not publish a container port and assume it works:
# use reviewed host networking, or the documented host systemd deployment.
CMD ["python", "-B", "-m", "app.server"]
