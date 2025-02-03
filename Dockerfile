FROM ubuntu:22.04

# Set non-interactive frontend for apt
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install required dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-venv libaugeas0 nginx openssl curl software-properties-common tzdata wget \
    && apt-get clean

# Set the timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory
WORKDIR /opt/arcadescore

# Copy application files
COPY ./app /opt/arcadescore/app
COPY ./certs /etc/ssl/certs
COPY ./config/nginx.conf /etc/nginx/sites-enabled/default
COPY ./config/gunicorn.conf.py /opt/arcadescore/config/gunicorn.conf.py
COPY ./requirements.txt /opt/arcadescore/requirements.txt
COPY ./run.py /opt/arcadescore/run.py
COPY ./entrypoint.sh /usr/local/bin/entrypoint.sh
COPY ./pre_start.sh /usr/local/bin/pre_start.sh

# Create a Python virtual environment for the app and install dependencies
RUN python3 -m venv /opt/arcadescore/venv && \
    /opt/arcadescore/venv/bin/pip install --upgrade pip && \
    /opt/arcadescore/venv/bin/pip install -r /opt/arcadescore/requirements.txt

# Ensure pre_start & entrypoint scripts are executable
RUN chmod +x /usr/local/bin/pre_start.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose ports for HTTP and HTTPS
EXPOSE 80 443

# Use the entrypoint script to manage services
CMD ["sh", "-c", "/usr/local/bin/pre_start.sh &&/usr/local/bin/entrypoint.sh"]
