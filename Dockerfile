FROM alpine:edge
LABEL org.opencontainers.image.source https://github.com/satcom886/router_prometheus

RUN mkdir -p /app/config /app/src
ADD src /app/src
WORKDIR /app

RUN echo https://dl-cdn.alpinelinux.org/alpine/edge/testing/ | tee -a /etc/apk/repositories
RUN apk add curl python3 py3-yaml py3-prometheus-client fabric

# The port instide the container must remain set to 8080 in order for this healthcheck to work
HEALTHCHECK --interval=60s --timeout=4s CMD curl -f http://localhost:8080/ || exit 1
CMD env python3 src/main.py
