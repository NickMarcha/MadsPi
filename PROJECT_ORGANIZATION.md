# MadsPipeline Project Organization

## 📁 **Project Structure**

```
MadsPipline/
├── 📁 src/                           # Source code
│   └── 📁 madspipeline/              # Main package
│       ├── __init__.py               # Package initialization
│       ├── main.py                   # Main application entry point
│       ├── main_window.py            # Main window and GUI components
│       ├── models.py                 # Data models and classes
│       └── project_manager.py        # Project management functionality
├── 📁 tests/                         # Test suite
│   ├── __init__.py                   # Test package initialization
│   ├── 📁 unit/                      # Unit tests
│   │   ├── __init__.py
│   │   ├── test_models.py           # Model and enum tests
│   │   └── test_gui.py              # GUI component tests
│   ├── 📁 integration/               # Integration tests
│   │   ├── __init__.py
│   │   ├── test_embedded_webpage.py # Webpage project tests
│   │   └── test_embedded_webpage_session.py # Session tests
│   └── 📁 fixtures/                  # Test data and fixtures
│       ├── __init__.py
│       └── test_webpage.html        # Test HTML file
├── 📁 .vscode/                       # VS Code configuration
│   ├── settings.json                 # Python development settings
│   ├── launch.json                   # Debug configurations
│   ├── tasks.json                    # Build and test tasks
│   └── extensions.json               # Recommended extensions
├── 📁 scripts/                       # Setup and utility scripts
├── 📁 .venv/                         # Python virtual environment
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Development dependencies
├── pyproject.toml                    # Modern Python project configuration
├── pytest.ini                        # PyTest configuration
├── run.py                            # Application launcher
├── README.md                          # Project documentation
├── TODO.md                           # Development tasks
└── LICENCE                           # MIT License
```

## 🚀 **VS Code/Cursor Integration**

### **Debug Configurations** (launch.json)

- **Launch Main Application**: Run the main app directly
- **Launch with run.py**: Use the launcher script
- **Debug Current Test File**: Debug any test file you have open
- **Run All Tests**: Execute the complete test suite
- **Run Unit Tests**: Execute only unit tests
- **Run Integration Tests**: Execute only integration tests

### **Build Tasks** (tasks.json)

- **Run All Tests**: Execute complete test suite
- **Run Unit Tests**: Execute unit tests only
- **Run Integration Tests**: Execute integration tests only
- **Run Main Application**: Launch the application
- **Install Dev Dependencies**: Install development packages

### **Python Settings** (settings.json)

- Auto-formatting with Black (88 character line length)
- Linting with Flake8
- Import sorting with isort
- PyTest integration
- Python path configuration
- Code analysis and type checking

### **Recommended Extensions** (extensions.json)

- Python language support
- Pylance (advanced Python language server)
- Black formatter
- Flake8 linter
- PyTest adapter
- Import sorting
- JSON and YAML support
- PowerShell support
- Markdown linting
- Spell checking

## 🧪 **Testing**

### **Test Organization**

- **Unit Tests** (`tests/unit/`): Test individual components in isolation
- **Integration Tests** (`tests/integration/`): Test component interactions
- **Fixtures** (`tests/fixtures/`): Test data and resources

### **Running Tests**

```bash
# Run all tests
python -m pytest tests -v

# Run unit tests only
python -m pytest tests/unit -v

# Run integration tests only
python -m pytest tests/integration -v

# Run specific test file
python tests/unit/test_models.py
```

### **Test Configuration** (pytest.ini)

- Test discovery in `tests/` directory
- Verbose output by default
- Custom markers for test categorization
- Warning filtering

## 🛠️ **Development Tools**

### **Code Quality**

- **Black**: Code formatting (88 character lines)
- **Flake8**: Linting and style checking
- **isort**: Import statement organization
- **MyPy**: Static type checking

### **Project Configuration** (pyproject.toml)

- Modern Python packaging standards
- Development and production dependencies
- Tool configurations (Black, isort, MyPy)
- PyTest configuration
- Build system requirements

## 📋 **Quick Start**

### **1. Setup Development Environment**

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install development dependencies
pip install -r requirements-dev.txt
```

### **2. Run Tests**

```bash
# Run all tests
python -m pytest tests -v

# Or use VS Code tasks (Ctrl+Shift+P → "Tasks: Run Task")
```

### **3. Launch Application**

```bash
# Using launcher script
python run.py

# Or directly
python src/madspipeline/main.py

# Or use VS Code launch configurations (F5)
```

### **4. Code Quality**

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## 🔧 **VS Code Shortcuts**

- **F5**: Start debugging (select configuration)
- **Ctrl+Shift+P**: Command palette
- **Ctrl+Shift+P → "Tasks: Run Task"**: Execute build tasks
- **Ctrl+Shift+P → "Python: Select Interpreter"**: Choose Python version
- **Ctrl+Shift+P → "Python: Run All Tests"**: Execute test suite

## 📚 **Additional Resources**

- **README.md**: Project overview and setup instructions
- **TODO.md**: Development roadmap and tasks
- **requirements.txt**: Production dependencies
- **requirements-dev.txt**: Development dependencies
- **LICENCE**: MIT License terms

## 🎯 **Benefits of New Organization**

1. **Cleaner Project Root**: Only essential files at top level
2. **Better Test Organization**: Logical separation of test types
3. **Professional Development Experience**: VS Code integration
4. **Easier Maintenance**: Clear structure for future development
5. **Better CI/CD**: Standard test structure for automation
6. **Team Collaboration**: Clear project organization for contributors
7. **Modern Python Standards**: pyproject.toml and pytest configuration
8. **Code Quality Tools**: Automated formatting, linting, and type checking
