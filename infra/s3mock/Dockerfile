FROM python:3.12-slim

WORKDIR /app
COPY server.py .

ENV PORT=4566
ENV DATA_DIR=/data

EXPOSE 4566

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:4566/health').status==200 else 1)"

CMD ["python", "-u", "server.py"]
