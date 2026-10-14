from setuptools import setup, find_packages

setup(
    name="slack-migrate",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "slack-bolt",
        "slack_sdk",
        "tabulate",
        "python-dotenv",
        "click",
    ],
    entry_points="""
        [console_scripts]
        slack-migrate=slack_migrate.cli:cli
    """,
)