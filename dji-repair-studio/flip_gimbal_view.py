"""Flip gimbal workspace. USB inventory is available; calibration is not."""
import json
import re
import tkinter as tk
from tkinter import ttk

class FlipGimbalView(ttk.Frame):
    def __init__(self,parent,firmware):
        super().__init__(parent,padding=8)
        self.columnconfigure(1,weight=1);self.rowconfigure(5,weight=1)
        ttk.Label(self,text='DJI Flip · calibración de taller del gimbal',font=('Segoe UI',13,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=5)
        ttk.Label(self,text='Firmware declarado (DJI Fly)').grid(row=1,column=0,sticky='w')
        self.firmware_entry=ttk.Entry(self,textvariable=firmware);self.firmware_entry.grid(row=1,column=1,sticky='ew',padx=8)
        ttk.Label(self,text='Objetivo: JointCoarse y LinearHall · pendientes de validar para Flip.\n'
                  'Faltan el protocolo de modo de taller y las peticiones/respuestas de calibración de este modelo.\n'
                  'No se ejecutan las rutinas de otro dron al seleccionar Flip.\n\n'
                  'Pulsa «Consultar FC y gimbal (Flip)», elige tu ZIP de perfil USB y guarda el ZIP de consulta.\n'
                  'Dos consultas de versión 00/01, sin reenvío. No calibra ni mueve el gimbal.',
                  wraplength=820,justify='left').grid(row=2,column=0,columnspan=2,sticky='w',pady=10)
        self.summary=tk.StringVar();ttk.Label(self,textvariable=self.summary,wraplength=820).grid(row=3,column=0,columnspan=2,sticky='w',pady=6)
        self.nodes=ttk.Treeview(self,columns=('product','driver','endpoints'),show='tree headings',height=5)
        self.nodes.heading('#0',text='Nodo');self.nodes.column('#0',width=90)
        for key,label,width in [('product','Nombre de Windows',290),('driver','Controlador',140),('endpoints','Endpoints observados',240)]:
            self.nodes.heading(key,text=label);self.nodes.column(key,width=width)
        self.nodes.grid(row=4,column=0,columnspan=2,sticky='ew')
        self.evidence=tk.Text(self,height=6,wrap='word',state='disabled',font=('Consolas',9))
        self.evidence.grid(row=5,column=0,columnspan=2,sticky='nsew',pady=8)
        self.clear()

    def clear(self):
        self.summary.set('Sin consulta de versiones en esta sesión. La calibración no está disponible.')
        for key,text in [('#0','Nodo'),('product','Nombre de Windows'),('driver','Controlador'),('endpoints','Endpoints observados')]:
            self.nodes.heading(key,text=text)
        self.nodes.delete(*self.nodes.get_children())
        self.evidence.configure(state='normal');self.evidence.delete('1.0','end');self.evidence.configure(state='disabled')

    def apply_report(self,data):
        self.clear();self.summary.set(data.get('detail','Sin resultado de lectura.'))
        descriptors={}
        for alias in data.get('descriptor_inventory',{}).get('aliases',[]):
            if not alias.get('complete') or not alias.get('pnp_instance_matches'):continue
            mi=alias.get('pnp_interface_number');labels=[]
            for cfg in alias.get('configurations',[]):
                for interface in cfg['interfaces']:
                    if interface['bInterfaceNumber']==mi:
                        ep=', '.join(f"{e['bEndpointAddress']:02X} {e['direction']}" for e in interface['endpoints'])
                        labels.append(f"C{cfg['bConfigurationValue']}/A{interface['bAlternateSetting']}: {ep}")
            descriptors.setdefault(mi,[]).extend(labels)
        for row in data.get('devices',[]):
            m=re.search(r'&MI_([0-9a-f]{2})',row['instance_id'],re.I)
            label='MI'+m[1].upper() if m else 'Padre USB'
            ep='; '.join(dict.fromkeys(descriptors.get(int(m[1],16),[]))) if m else ''
            self.nodes.insert('','end',text=label,values=(row.get('bus_product') or row.get('friendly_name') or '—',row.get('service') or '—',ep or '—'))
        self.evidence.configure(state='normal');self.evidence.insert('1.0',json.dumps(data,ensure_ascii=False,indent=2));self.evidence.configure(state='disabled')

    def apply_module_report(self,data):
        self.clear();self.summary.set(data.get('detail','Sin respuesta reconocida.'))
        for key,text in [('#0','Módulo'),('product','Hardware observado'),('driver','Versión de módulo'),('endpoints','Resultado')]:
            self.nodes.heading(key,text=text)
        for row in data.get('modules',[]):
            self.nodes.insert('','end',text=row['modulo'],values=(row.get('hardware','—'),row.get('firmware_modulo','—'),row['estado']))
        self.evidence.configure(state='normal');self.evidence.insert('1.0',json.dumps(data,ensure_ascii=False,indent=2));self.evidence.configure(state='disabled')
