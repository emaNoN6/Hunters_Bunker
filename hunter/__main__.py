# hunter/__main__.py

# This file makes the 'hunter' package directly runnable.
# When you run `python -m hunter`, this is the code that executes.

from .hunter_app import HunterApp

def main():
    """The main entry point for the application."""
    print("Launching Hunter's Command Console...")
    app = HunterApp()
    app.mainloop()

if __name__ == "__main__":
    main()
