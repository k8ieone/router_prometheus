FROM alpine:edge AS builder
ARG py=python3

ADD . /build
WORKDIR /build

RUN echo https://dl-cdn.alpinelinux.org/alpine/edge/testing/ | tee -a /etc/apk/repositories
RUN apk add $py
RUN ln -s /pypy/bin/pypy3 /usr/bin/
RUN $py -m ensurepip && $py -m pip install setuptools wheel
RUN apk add gcc make rust cargo openssl-dev python3-dev libffi-dev

RUN $py setup.py bdist_wheel
RUN $py -m pip wheel . -w dist


FROM alpine:edge AS runner
LABEL org.opencontainers.image.source https://github.com/satcom886/router_prometheus
ARG py=python3

RUN mkdir /config

RUN echo https://dl-cdn.alpinelinux.org/alpine/edge/testing/ | tee -a /etc/apk/repositories
RUN apk add curl $py
RUN ln -s /pypy/bin/pypy3 /usr/bin/

COPY --from=builder /build/dist /dist
RUN $py -m ensurepip && $py -m pip install --upgrade pip  && $py -m pip install /dist/* && $py -m pip uninstall -y pip && rm -r /dist

# The port instide the container must remain set to 8080 in order for this healthcheck to work
HEALTHCHECK --interval=60s --timeout=5s CMD curl -f http://localhost:8080/ || exit 1
CMD [$py, "-u", "-m", "router_prometheus"]
