import os
import ast
import importlib.metadata

def get_imports_from_file(file_path):
    """Extracts all imported modules from a Python file."""
    try:
        with open(file_path, "r") as file:
            node = ast.parse(file.read(), filename=file_path)
        return {alias.name for n in ast.walk(node) if isinstance(n, ast.Import) for alias in n.names} | \
               {n.module for n in ast.walk(node) if isinstance(n, ast.ImportFrom) and n.module}
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Skipping file {file_path} due to parsing error: {e}")
        return set()

def get_all_imports(directory):
    """Collects all imports from top-level Python files in a directory."""
    imports = set()
    for file in os.listdir(directory):
        if file.endswith(".py"):
            file_path = os.path.join(directory, file)
            if os.path.isfile(file_path):  # Ensure it's a file, not a directory
                imports.update(get_imports_from_file(file_path))
    return imports

def get_requirements(requirements_file):
    """Reads the requirements.txt file and returns a set of required packages."""
    with open(requirements_file, "r") as file:
        return {line.strip().split('==')[0] for line in file if line.strip() and not line.startswith('#')}

def add_missing_requirements(requirements_file, missing_imports):
    """Appends missing imports with versions to the requirements.txt file."""
    with open(requirements_file, "a") as file:
        for imp in missing_imports:
            try:
                # Get the installed version of the package
                version = importlib.metadata.version(imp)
                file.write(f"{imp}=={version}\n")
            except importlib.metadata.PackageNotFoundError:
                print(f"Warning: {imp} is not installed, adding without version.")
                file.write(f"{imp}\n")
    print(f"Added missing imports to {requirements_file}.")

def main():
    directory = '.'  # Directory to search for .py files
    requirements_file = 'requirements.txt'

    # Get all imports from top-level .py files
    all_imports = get_all_imports(directory)

    # Get all requirements from requirements.txt
    requirements = get_requirements(requirements_file)

    # Find missing imports
    missing_imports = all_imports - requirements

    if missing_imports:
        print("The following imports are missing from requirements.txt and will be added:")
        for imp in missing_imports:
            print(imp)
        add_missing_requirements(requirements_file, missing_imports)
    else:
        print("All imports are covered in requirements.txt.")

if __name__ == "__main__":
    main()