import setuptools  # type: ignore

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="router_prometheus",
    version="0.2.3",
    author="satcom886",
    author_email="rostik.medved@gmail.com",
    description="Get metrics from various consumer routers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/satcom886/router_prometheus",
    project_urls={
        "Bug Tracker": "https://github.com/satcom886/router_prometheus/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(include=["router_prometheus"]),
    entry_points={
        "console_scripts": [
            "router_prometheus = router_prometheus.main:main"
        ]
    },
    install_requires=["PyYAML", "fabric", "prometheus_client"],
    python_requires=">=3.6"
)
