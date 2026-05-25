from setuptools import setup, find_packages

setup(
    name="voice-line",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "faster-whisper>=1.0.0",
        "pydub>=0.25.0",
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
    ],
    entry_points={
        "console_scripts": [
            "voice-line=voice_line.cli:main",
        ],
    },
    python_requires=">=3.9",
)
