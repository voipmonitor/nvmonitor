from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nvmonitor",
    version="1.0.0",
    author="VoIPmonitor",
    description="Real-time NVIDIA GPU throttle monitoring tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/voipmonitor/nvmonitor",
    py_modules=["nvmonitor"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Hardware",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.6",
    extras_require={
        "nvml": ["pynvml"],
    },
    entry_points={
        "console_scripts": [
            "nvmonitor=nvmonitor:main",
        ],
    },
)