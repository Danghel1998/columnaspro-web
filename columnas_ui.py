import tkinter as tk
from tkinter import ttk, messagebox
from calculo_columnas import CalculadoraColumnas

class ColumnasUI:
    def __init__(self, parent_frame):
        self.frame = parent_frame
        self.calculadora = CalculadoraColumnas()
        
        self.crear_widgets()

    def crear_widgets(self):
        # --- Frame Izquierdo: Entradas de Datos ---
        frame_inputs = ttk.LabelFrame(self.frame, text="Datos de Entrada")
        frame_inputs.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Geometría
        ttk.Label(frame_inputs, text="Geometría", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(frame_inputs, text="Base b (cm):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_b = ttk.Entry(frame_inputs, width=10)
        self.entry_b.insert(0, "30")
        self.entry_b.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(frame_inputs, text="Altura h (cm):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_h = ttk.Entry(frame_inputs, width=10)
        self.entry_h.insert(0, "40")
        self.entry_h.grid(row=2, column=1, padx=5, pady=2)

        # Materiales
        ttk.Label(frame_inputs, text="Materiales", font=("Arial", 10, "bold")).grid(row=3, column=0, columnspan=2, pady=5)
        
        ttk.Label(frame_inputs, text="f'c (kgf/cm²):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_fc = ttk.Entry(frame_inputs, width=10)
        self.entry_fc.insert(0, "210")
        self.entry_fc.grid(row=4, column=1, padx=5, pady=2)

        ttk.Label(frame_inputs, text="fy (kgf/cm²):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_fy = ttk.Entry(frame_inputs, width=10)
        self.entry_fy.insert(0, "4200")
        self.entry_fy.grid(row=5, column=1, padx=5, pady=2)

        # Cargas
        ttk.Label(frame_inputs, text="Cargas de Diseño", font=("Arial", 10, "bold")).grid(row=6, column=0, columnspan=2, pady=5)
        
        ttk.Label(frame_inputs, text="Pu (Ton):").grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_pu = ttk.Entry(frame_inputs, width=10)
        self.entry_pu.insert(0, "100")
        self.entry_pu.grid(row=7, column=1, padx=5, pady=2)

        ttk.Label(frame_inputs, text="Mux (Ton-m):").grid(row=8, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_mux = ttk.Entry(frame_inputs, width=10)
        self.entry_mux.insert(0, "5")
        self.entry_mux.grid(row=8, column=1, padx=5, pady=2)

        ttk.Label(frame_inputs, text="Muy (Ton-m):").grid(row=9, column=0, sticky=tk.W, padx=5, pady=2)
        self.entry_muy = ttk.Entry(frame_inputs, width=10)
        self.entry_muy.insert(0, "2")
        self.entry_muy.grid(row=9, column=1, padx=5, pady=2)

        # Botón Calcular
        btn_calcular = ttk.Button(frame_inputs, text="Calcular y Dibujar", command=self.ejecutar_calculo)
        btn_calcular.grid(row=10, column=0, columnspan=2, pady=15)

        # --- Frame Derecho: Gráficos y Resultados ---
        frame_der = ttk.Frame(self.frame)
        frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas para dibujar sección
        frame_grafico = ttk.LabelFrame(frame_der, text="Sección de la Columna")
        frame_grafico.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(frame_grafico, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Resultados
        frame_resultados = ttk.LabelFrame(frame_der, text="Resultados del Análisis")
        frame_resultados.pack(fill=tk.X, pady=10)

        self.txt_resultados = tk.Text(frame_resultados, height=6, width=40)
        self.txt_resultados.pack(fill=tk.X, padx=5, pady=5)
        self.txt_resultados.config(state=tk.DISABLED)
        
        # Dibujo inicial
        self.dibujar_seccion(30, 40)

    def ejecutar_calculo(self):
        try:
            b = float(self.entry_b.get())
            h = float(self.entry_h.get())
            fc = float(self.entry_fc.get())
            fy = float(self.entry_fy.get())
            pu = float(self.entry_pu.get())
            mux = float(self.entry_mux.get())
            muy = float(self.entry_muy.get())
            
            # Ejecutar lógica de cálculo
            resultados = self.calculadora.calcular_area_acero_aproximada(b, h, fc, fy, pu, mux, muy)
            
            # Mostrar resultados
            self.txt_resultados.config(state=tk.NORMAL)
            self.txt_resultados.delete(1.0, tk.END)
            self.txt_resultados.insert(tk.END, f"Área bruta (Ag): {resultados['area_bruta_cm2']:.2f} cm²\n")
            self.txt_resultados.insert(tk.END, f"Cuantía mínima (1%): {resultados['cuantia_minima_cm2']:.2f} cm²\n")
            self.txt_resultados.insert(tk.END, f"Estado: {resultados['estado']}\n")
            self.txt_resultados.config(state=tk.DISABLED)
            
            # Actualizar dibujo
            self.dibujar_seccion(b, h)
            
        except ValueError:
            messagebox.showerror("Error de Entrada", "Por favor, ingrese valores numéricos válidos en todos los campos.")

    def dibujar_seccion(self, b, h):
        self.canvas.delete("all")
        
        # Obtener dimensiones del canvas (estimado si no está renderizado)
        self.canvas.update()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        if canvas_w <= 1 or canvas_h <= 1:
            canvas_w, canvas_h = 300, 300
            
        # Escalar el dibujo para que quepa en el canvas
        margen = 40
        max_dim = max(b, h)
        if max_dim == 0: return
        
        escala = min((canvas_w - 2*margen) / b, (canvas_h - 2*margen) / h)
        
        w_px = b * escala
        h_px = h * escala
        
        x0 = (canvas_w - w_px) / 2
        y0 = (canvas_h - h_px) / 2
        x1 = x0 + w_px
        y1 = y0 + h_px
        
        # Dibujar concreto
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="lightgray", outline="black", width=2)
        
        # Dibujar cotas
        self.canvas.create_text(canvas_w/2, y1 + 15, text=f"b = {b} cm")
        self.canvas.create_text(x0 - 25, canvas_h/2, text=f"h =\n{h} cm", justify=tk.CENTER)
