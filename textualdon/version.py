import re

__version__ = "0.1.7"

if __name__ == "__main__":

    with open("README.md", "r") as f:
        content = f.read()

    # Note the two regex patterns in this script are slightly different
    updated_content = re.sub(r'version:\s*(\d+\.\d+\.\d+)', f'version: {__version__}', content)

    with open("README.md", "w") as f:
        f.write(updated_content)

    with open("pyproject.toml", "r") as f:
        content = f.read()

    updated_content = re.sub(r'version\s*=\s*"(\d+\.\d+\.\d+)"', f'version = "{__version__}"', content)

    with open("pyproject.toml", "w") as f:
        f.write(updated_content)