FROM debian:testing AS builder
ARG py=python3
ENV py=$py

RUN apt update && apt install -y $py wget python3-distutils $py-venv
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN $py get-pip.py --break-system-packages

ADD . /build
WORKDIR /build

RUN $py -m pip install setuptools --break-system-packages

RUN apt install -y gcc make rustc cargo libffi-dev libssl-dev $py-dev

RUN $py -m venv /venv
ENV PATH=/venv/bin:$PATH
RUN $py -m pip install setuptools-rust wheel
RUN $py ./setup.py bdist_wheel
RUN $py -m pip wheel . -w dist


FROM debian:testing AS runner
LABEL org.opencontainers.image.source https://github.com/a13xie/router_prometheus
ARG py=python3
ENV py=$py

RUN mkdir /config

RUN apt update && apt install -y curl $py $py-venv
COPY --from=builder /venv /venv
ENV PATH=/venv/bin:$PATH

COPY --from=builder /build/dist /dist
RUN $py -m pip install /dist/* && $py -m pip uninstall -y pip && rm -r /dist

# The port inside the container must remain set to 9000 in order for this healthcheck to work
HEALTHCHECK --interval=60s CMD curl -f --max-time 5 http://localhost:9000/ || exit 1
CMD ["python", "-u", "-m", "router_prometheus"]
