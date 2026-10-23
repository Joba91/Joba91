"""Tk widgets only; file/protocol/network work stays in independent modules."""
import json
import tkinter as tk
from tkinter import ttk
from vision_interfaces import UnavailableIdentification, LocalCalibrationProvider

class VisionView(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=8)
        self.reports={};self.url=tk.StringVar();self.timeout=tk.StringVar(value='5')
        self.format=tk.StringVar(value='auto');self.source=tk.StringVar(value='Ningún paquete importado')
        self.columnconfigure(0,weight=1);self.rowconfigure(4,weight=1)
        ttk.Label(self,text='Mini 4 Pro · diagnóstico de visión sin conexión',font=('Segoe UI',12,'bold')).grid(row=0,column=0,sticky='w')
        ttk.Label(self,text='Implementación propia. No ejecuta DJI Test.exe ni carga DLL del paquete. Escritura y lectura USB de visión deshabilitadas.',wraplength=860).grid(row=1,column=0,sticky='w',pady=(4,6))
        self.states=ttk.Treeview(self,columns=('state','detail'),show='tree headings',height=6)
        self.states.heading('#0',text='Comprobación');self.states.column('#0',width=130,minwidth=110,stretch=False)
        self.states.heading('state',text='Estado');self.states.column('state',width=105,stretch=False)
        self.states.heading('detail',text='Resultado / procedencia');self.states.column('detail',width=460)
        self.states.grid(row=2,column=0,sticky='ew',pady=5)
        form=ttk.Frame(self);form.grid(row=3,column=0,sticky='ew');form.columnconfigure(1,weight=1)
        ttk.Label(form,text='Servidor autorizado (HTTPS)').grid(row=0,column=0,sticky='w')
        url_entry=ttk.Entry(form,textvariable=self.url);url_entry.grid(row=0,column=1,sticky='ew',padx=8)
        ttk.Label(form,text='Máximo (s)').grid(row=0,column=2)
        timeout_entry=ttk.Combobox(form,textvariable=self.timeout,values=('3','5','10'),width=5,state='readonly');timeout_entry.grid(row=0,column=3)
        ttk.Label(form,text='Formato de captura').grid(row=1,column=0,sticky='w',pady=5)
        format_entry=ttk.Combobox(form,textvariable=self.format,values=('auto','binary','hexlog'),state='readonly',width=14);format_entry.grid(row=1,column=1,sticky='w',padx=8)
        self.controls=[(url_entry,'normal'),(timeout_entry,'readonly'),(format_entry,'readonly')]
        tabs=ttk.Notebook(self);tabs.grid(row=4,column=0,sticky='nsew',pady=5)
        files=ttk.Frame(tabs);files.columnconfigure(0,weight=1);files.rowconfigure(1,weight=1);tabs.add(files,text='Inventario local')
        ttk.Label(files,textvariable=self.source,wraplength=800).grid(row=0,column=0,sticky='w',pady=5)
        self.inventory=ttk.Treeview(files,columns=('size','digest','state'),show='tree headings')
        self.inventory.heading('#0',text='Archivo (primeros 500)');self.inventory.column('#0',width=270)
        for key,label,width in [('size','Bytes',75),('digest','MD5 calculado',220),('state','Lectura',100)]:
            self.inventory.heading(key,text=label);self.inventory.column(key,width=width)
        self.inventory.grid(row=1,column=0,sticky='nsew');scroll=ttk.Scrollbar(files,command=self.inventory.yview);scroll.grid(row=1,column=1,sticky='ns');self.inventory.configure(yscrollcommand=scroll.set)
        detail=ttk.Frame(tabs);detail.columnconfigure(0,weight=1);detail.rowconfigure(0,weight=1);tabs.add(detail,text='Resultados y evidencia')
        self.details=tk.Text(detail,wrap='word',font=('Consolas',9),state='disabled');self.details.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(detail,command=self.details.yview);scroll.grid(row=0,column=1,sticky='ns');self.details.configure(yscrollcommand=scroll.set)
        ttk.Label(self,text='Acciones en el lateral. El servidor solo se consulta al solicitarlo. MD5 no acredita autenticidad ni compatibilidad. Guardar informe conserva todos los resultados.',wraplength=850).grid(row=5,column=0,sticky='w',pady=5)
        self.refresh_states()

    def apply_report(self,category,data):
        self.reports[category]=data
        if category=='package':
            self.inventory.delete(*self.inventory.get_children())
            if 'files' in data:
                self.source.set(f"{data['source']} · {data['kind']} · {data['file_count']} archivos")
                for f in data['files'][:500]:
                    self.inventory.insert('', 'end',text=f['path'],values=(f['size'],f.get('md5','—'),'error' if f.get('error') else 'leído'))
            else:self.source.set('La importación falló; vuelve a seleccionar un paquete')
        self.refresh_states()
        preview={**data}
        if 'files' in preview:preview['files']=preview['files'][:200];preview['preview_files_limit']=200
        self.details.configure(state='normal');self.details.delete('1.0','end')
        self.details.insert('1.0',json.dumps(preview,ensure_ascii=False,indent=2));self.details.configure(state='disabled')

    def refresh_states(self):
        self.states.delete(*self.states.get_children())
        identity=self.reports.get('identity',UnavailableIdentification().identify().to_dict())
        package=self.reports.get('package',{})
        compatibility=LocalCalibrationProvider().compatibility(package,None).to_dict()
        unknown={'state':'desconocido','detail':'Sin datos; utiliza las acciones del lateral.'}
        source={'state':'confirmado' if 'files' in package else package.get('state','desconocido'),'detail':package.get('source','Ningún paquete importado')}
        rows=[('Identificación',identity),('Procedencia',source),('Integridad MD5',package.get('integrity',package if package else unknown)),
              ('Compatibilidad',compatibility),('Captura',self.reports.get('capture',unknown)),('Servidor',self.reports.get('server',unknown))]
        for title,data in rows:self.states.insert('', 'end',text=title,values=(data['state'],data['detail']))
