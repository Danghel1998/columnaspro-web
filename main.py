import tkinter as tk
from tkinter import ttk
from columnas_ui import ColumnasUI

class AplicacionPrincipal:
    def __init__(self, root):
        self.root = root
        self.root.title("Software de Diseño Estructural - Columnas y Zapatas")
        self.root.geometry("800x600")
        
        # Crear el Notebook (pestañas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestaña de Columnas
        self.tab_columnas = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_columnas, text="Diseño de Columnas")
        
        # Inicializar la UI de columnas
        self.columnas_ui = ColumnasUI(self.tab_columnas)
        
        # Pestaña de Zapatas (Placeholder por ahora)
        self.tab_zapatas = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_zapatas, text="Diseño de Zapatas")
        ttk.Label(self.tab_zapatas, text="Interfaz de Zapatas en desarrollo...").pack(pady=50)

if __name__ == "__main__":
    root = tk.Tk()
    
    # Aplicar un estilo básico
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
        
    app = AplicacionPrincipal(root)
    root.mainloop()
