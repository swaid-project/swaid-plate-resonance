"""Entry point: python -m simulator"""

import tkinter as tk
from .gui import ChladniApp


def main():
    root = tk.Tk()
    ChladniApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
