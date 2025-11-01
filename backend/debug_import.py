import sys
import importlib.util

def check_module_import(module_name):
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            print(f"{module_name} can be imported")
            module = __import__(module_name)
            print(f"Module location: {module.__file__}")
        else:
            print(f"{module_name} cannot be found")
    except Exception as e:
        print(f"Error importing {module_name}: {e}")

# Modules to check
modules = ['structlog', 'pydantic', 'fastapi', 'uvicorn', 'langchain']

print("Python Path:", sys.path)
print("\nModule Import Check:")
for module in modules:
    check_module_import(module)