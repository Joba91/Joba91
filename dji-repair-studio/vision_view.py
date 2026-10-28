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
        self.firmware=tk.StringVar();self.capture_seconds=tk.StringVar(value='5')
        self.engine_directory=tk.StringVar();self.image_references=[];self.image_sources={};self.image_scale=None
        self.columnconfigure(0,weight=1);self.rowconfigure(4,weight=1)
        ttk.Label(self,text='Mini 4 Pro · visión, SN y diagnóstico HMS experimental',font=('Segoe UI',12,'bold')).grid(row=0,column=0,sticky='w')
        ttk.Label(self,text='Conserva modo normal y cierra otros clientes USB. Diagnóstico HMS solicita publicación de estados; su soporte en Mini 4 Pro está pendiente de prueba. Presenta códigos y niveles, sin afirmar salud o calibración.',wraplength=860).grid(row=1,column=0,sticky='w',pady=(4,6))
        state_area=ttk.Frame(self);state_area.grid(row=2,column=0,sticky='ew',pady=5);state_area.columnconfigure(0,weight=1)
        self.states=ttk.Treeview(state_area,columns=('state','detail'),show='tree headings',height=3)
        self.states.heading('#0',text='Comprobación');self.states.column('#0',width=130,minwidth=110,stretch=False)
        self.states.heading('state',text='Estado');self.states.column('state',width=105,stretch=False)
        self.states.heading('detail',text='Resultado / procedencia');self.states.column('detail',width=460)
        self.states.grid(row=0,column=0,sticky='ew')
        state_scroll=ttk.Scrollbar(state_area,command=self.states.yview);state_scroll.grid(row=0,column=1,sticky='ns');self.states.configure(yscrollcommand=state_scroll.set)
        form=ttk.Frame(self);form.grid(row=3,column=0,sticky='ew');form.columnconfigure(1,weight=1)
        ttk.Label(form,text='Servidor autorizado (HTTPS)').grid(row=0,column=0,sticky='w')
        url_entry=ttk.Entry(form,textvariable=self.url);url_entry.grid(row=0,column=1,sticky='ew',padx=8)
        ttk.Label(form,text='Máximo (s)').grid(row=0,column=2)
        timeout_entry=ttk.Combobox(form,textvariable=self.timeout,values=('3','5','10'),width=5,state='readonly');timeout_entry.grid(row=0,column=3)
        ttk.Label(form,text='Formato de captura').grid(row=1,column=0,sticky='w',pady=5)
        format_entry=ttk.Combobox(form,textvariable=self.format,values=('auto','binary','hexlog','djilog'),state='readonly',width=14);format_entry.grid(row=1,column=1,sticky='w',padx=8)
        self.controls=[(url_entry,'normal'),(timeout_entry,'readonly'),(format_entry,'readonly')]
        ttk.Label(form,text='Firmware declarado (DJI Fly)').grid(row=2,column=0,sticky='w',pady=5)
        firmware_entry=ttk.Entry(form,textvariable=self.firmware,width=16);firmware_entry.grid(row=2,column=1,sticky='w',padx=8)
        ttk.Label(form,text='Captura pasiva (s)').grid(row=2,column=2)
        capture_entry=ttk.Combobox(form,textvariable=self.capture_seconds,values=('5','10'),state='readonly',width=5);capture_entry.grid(row=2,column=3)
        self.controls.extend([(firmware_entry,'normal'),(capture_entry,'readonly')])
        ttk.Label(form,text='Motor Consumer (DJIEngine)').grid(row=3,column=0,sticky='w',pady=4)
        engine_entry=ttk.Entry(form,textvariable=self.engine_directory);engine_entry.grid(row=3,column=1,columnspan=3,sticky='ew',padx=8)
        self.controls.append((engine_entry,'normal'))
        tabs=ttk.Notebook(self);tabs.grid(row=4,column=0,sticky='nsew',pady=5)
        self.tabs=tabs
        image_page=ttk.Frame(tabs);image_page.columnconfigure(0,weight=1);image_page.columnconfigure(1,weight=1)
        tabs.add(image_page,text='Imágenes (prueba)');self.image_page=image_page
        image_page.rowconfigure(2,weight=1)
        image_page.bind('<Configure>',lambda event:self.resize_previews())
        self.image_summary=tk.StringVar(value='Recibir imágenes (prueba) usa el motor Consumer local y guarda dos canales inferiores. No calibra.')
        ttk.Label(image_page,textvariable=self.image_summary,wraplength=810).grid(row=0,column=0,columnspan=2,sticky='w',pady=5)
        self.image_labels=[]
        for index,label in enumerate(('raw/down/left','raw/down/right')):
            ttk.Label(image_page,text=label).grid(row=1,column=index,pady=3)
            view=ttk.Label(image_page,text='Sin fotograma recibido',anchor='center');view.grid(row=2,column=index,sticky='nsew',padx=4,pady=4);self.image_labels.append(view)
        ttk.Label(image_page,text='Los canales siguen la referencia del motor. Las imágenes no confirman identidad, salud ni calibración.',wraplength=810).grid(row=3,column=0,columnspan=2,sticky='w',pady=5)
        diagnostic=ttk.Frame(tabs);diagnostic.columnconfigure(0,weight=1);diagnostic.rowconfigure(1,weight=1)
        tabs.add(diagnostic,text='Diagnóstico HMS');self.hms_page=diagnostic
        self.hms_summary=tk.StringVar(value='Pulsa Diagnóstico visión (HMS). Solicita estados y escucha 8 segundos; no inicia calibración.')
        ttk.Label(diagnostic,textvariable=self.hms_summary,wraplength=820).grid(row=0,column=0,sticky='w',pady=5)
        self.hms_records=ttk.Treeview(diagnostic,columns=('sender','sensor','level','cycle','description','format','activity'),show='tree headings',height=4)
        self.hms_records.heading('#0',text='Código informado');self.hms_records.column('#0',width=130)
        for key,label,width in [('sender','Emisor',55),('sensor','Índice',45),('level','Nivel bruto',70),('cycle','Ciclo',75),('description','Referencia / sin confirmar actividad',300),('format','Formato',65),('activity','Actividad',90)]:
            self.hms_records.heading(key,text=label);self.hms_records.column(key,width=width)
        self.hms_records.grid(row=1,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(diagnostic,command=self.hms_records.yview);scroll.grid(row=1,column=1,sticky='ns')
        self.hms_records.configure(yscrollcommand=scroll.set)
        ttk.Label(diagnostic,text='Un código presente no confirma fallo activo. Las descripciones son referencias del SDK, sin validación específica Mini 4 Pro. En 21/08, índice/nivel/actividad siguen sin interpretar. Ciclos vacíos no prueban salud.',wraplength=820).grid(row=2,column=0,sticky='w',pady=5)
        current=ttk.Frame(tabs);current.columnconfigure(0,weight=1);current.rowconfigure(1,weight=1)
        tabs.add(current,text='Consulta SN (prueba)');self.current_sensor_page=current
        self.current_sensor_summary=tk.StringVar(value='Usa Consultar SN visión (prueba) en el lateral; guarda un .bin nuevo para generar el ZIP de resultados.')
        ttk.Label(current,textvariable=self.current_sensor_summary,wraplength=820).grid(row=0,column=0,sticky='w',pady=5)
        self.current_sensor_records=ttk.Treeview(current,columns=('serial','status'),show='tree headings',height=4)
        self.current_sensor_records.heading('#0',text='Selector / posición histórica');self.current_sensor_records.column('#0',width=240)
        self.current_sensor_records.heading('serial',text='SN observado');self.current_sensor_records.column('serial',width=200)
        self.current_sensor_records.heading('status',text='Resultado experimental');self.current_sensor_records.column('status',width=300)
        self.current_sensor_records.grid(row=1,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(current,command=self.current_sensor_records.yview)
        scroll.grid(row=1,column=1,sticky='ns');self.current_sensor_records.configure(yscrollcommand=scroll.set)
        ttk.Label(current,text='Los SN son observaciones del tráfico recibido durante la prueba. Correlación, posición física e identidad no confirmadas. Ausencia de respuesta no implica avería. El porcentaje cuenta ventanas, no salud.',wraplength=820).grid(row=2,column=0,sticky='w',pady=5)
        files=ttk.Frame(tabs);files.columnconfigure(0,weight=1);files.rowconfigure(1,weight=1);tabs.add(files,text='Inventario local')
        ttk.Label(files,textvariable=self.source,wraplength=800).grid(row=0,column=0,sticky='w',pady=5)
        self.inventory=ttk.Treeview(files,columns=('size','digest','state'),show='tree headings')
        self.inventory.heading('#0',text='Archivo (primeros 500)');self.inventory.column('#0',width=270)
        for key,label,width in [('size','Bytes',75),('digest','MD5 calculado',220),('state','Lectura',100)]:
            self.inventory.heading(key,text=label);self.inventory.column(key,width=width)
        self.inventory.grid(row=1,column=0,sticky='nsew');scroll=ttk.Scrollbar(files,command=self.inventory.yview);scroll.grid(row=1,column=1,sticky='ns');self.inventory.configure(yscrollcommand=scroll.set)
        sensors=ttk.Frame(tabs);sensors.columnconfigure(0,weight=1);sensors.rowconfigure(1,weight=1)
        tabs.add(sensors,text='Sensores del registro');self.sensor_page=sensors
        self.sensor_summary=tk.StringVar(value='Importa un registro con las acciones del lateral.')
        ttk.Label(sensors,textvariable=self.sensor_summary,wraplength=820).grid(row=0,column=0,sticky='w',pady=5)
        self.sensor_records=ttk.Treeview(sensors,columns=('serial','label','line'),show='tree headings')
        self.sensor_records.heading('#0',text='Posición histórica');self.sensor_records.column('#0',width=150)
        for key,label,width in [('serial','SN desde payload',180),('label','Contraste con etiqueta',210),('line','Línea / offset',85)]:
            self.sensor_records.heading(key,text=label);self.sensor_records.column(key,width=width)
        self.sensor_records.grid(row=1,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(sensors,command=self.sensor_records.yview);scroll.grid(row=1,column=1,sticky='ns');self.sensor_records.configure(yscrollcommand=scroll.set)
        self.sensor_provenance=tk.StringVar(value='Datos históricos. No identifican el dron conectado ni confirman salud, calibración o éxito de comandos.')
        ttk.Label(sensors,textvariable=self.sensor_provenance,wraplength=820).grid(row=2,column=0,sticky='w',pady=5)
        detail=ttk.Frame(tabs);detail.columnconfigure(0,weight=1);detail.rowconfigure(0,weight=1);tabs.add(detail,text='Resultados y evidencia')
        self.details=tk.Text(detail,wrap='word',font=('Consolas',9),state='disabled');self.details.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(detail,command=self.details.yview);scroll.grid(row=0,column=1,sticky='ns');self.details.configure(yscrollcommand=scroll.set)
        ttk.Label(self,text='HMS, SN y captura pasiva crean un ZIP local con recepción e informe. Comparte el ZIP generado para revisar la prueba. Guardar informe exporta JSON.',wraplength=850).grid(row=5,column=0,sticky='w',pady=5)
        self.refresh_states()

    def apply_report(self,category,data):
        self.reports[category]=data
        if category=='images':
            self.image_references=[];self.image_sources={};self.image_scale=None
            for label in self.image_labels:label.configure(image='',text='Sin fotograma recibido')
            self.image_summary.set(data.get('detail','Sin resultado de imágenes.'))
            roles={'raw/down/left':0,'raw/down/right':1}
            for frame in data.get('frames',[]):
                try:
                    index=roles[frame['topic']]
                    self.image_sources[index]=tk.PhotoImage(file=frame['image_path'])
                except (tk.TclError,KeyError):
                    self.image_summary.set(data.get('detail','')+' Vista previa no disponible; consulta el ZIP.')
            self.tabs.select(self.image_page)
            self.resize_previews()
        if category in ('diagnostic','capture'):
            hms=data.get('hms',{})
            self.hms_records.delete(*self.hms_records.get_children())
            provenance='Consulta HMS actual' if category=='diagnostic' else 'Recepción pasiva actual' if data.get('origin')=='live_usb_passive' else 'Archivo local'
            self.hms_summary.set(f"{provenance} · {hms.get('packets_seen',0)} mensajes · {hms.get('complete_cycles',0)} ciclos completos de referencia · "
                f"{hms.get('distinct_records_shown',0)} registros distintos. Salud desconocida."+(' Error: '+data['error'] if data.get('error') else ''))
            for record in hms.get('records_preview',[]):
                self.hms_records.insert('', 'end',text=record['alarm_code_raw'],values=(record['sender_raw'],
                    record['sensor_index_raw'] if record['sensor_index_raw'] is not None else '—',
                    record['report_level_raw'] if record['report_level_raw'] is not None else '—',
                    'completo' if record['seen_in_complete_cycle'] else 'incompleto',record['description'],
                    '21/'+record.get('command_id_raw','06'),record.get('alarm_activity','desconocido')))
            if category=='diagnostic' or hms.get('packets_seen'):self.tabs.select(self.hms_page)
        if category=='identity':
            self.current_sensor_records.delete(*self.current_sensor_records.get_children())
            rows=data.get('queries',[])
            observed=sum(bool(q.get('serials_observed')) for q in rows)
            summary=('Error: '+data['error']) if data.get('error') else 'Correlación e identidad sin confirmar.'
            self.current_sensor_summary.set(f'{observed}/4 selectores con SN observado · '+summary)
            for row in rows:
                self.current_sensor_records.insert('', 'end',text=f"0x{row['selector']:02X} / {row.get('role_historical','desconocida')}",
                    values=(', '.join(row.get('serials_observed',[])) or 'sin SN reconocido',row.get('observation_status',row.get('query_status','desconocido'))))
            self.tabs.select(self.current_sensor_page)
        if category=='capture':
            live=data.get('origin')=='live_usb_passive'
            self.sensor_provenance.set('Recepción USB actual; la asignación de posiciones procede de registros históricos. No confirma salud, calibración ni respuesta a una consulta.' if live else
                'Datos históricos o archivo local. No identifican el dron conectado ni confirman salud, calibración o éxito de comandos.')
            self.sensor_records.delete(*self.sensor_records.get_children())
            records=data.get('perception_records',{});counts=records.get('counts',{})
            self.sensor_summary.set(f"{counts.get('decoded',0)} SN convertidos · {counts.get('label_matches',0)} etiquetas coincidentes · "
                f"{counts.get('label_mismatches',0)} diferencias · {counts.get('unknown_layout_or_invalid_serial',0)} sin SN válido · vista: 200 máx.")
            for record in records.get('observations_preview',[]):
                self.sensor_records.insert('', 'end',text=record.get('role_historical','desconocida'),values=(
                    record.get('serial_from_payload','desconocido'),record['label_comparison'],record['line']))
            if counts.get('records'):self.tabs.select(self.sensor_page)
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

    def resize_previews(self):
        if not self.image_sources:return
        import math
        width=max(64,(self.image_page.winfo_width()-24)//2)
        height=max(48,self.image_page.winfo_height()-110)
        scale=max(2,math.ceil(640/width),math.ceil(480/height))
        if scale==self.image_scale:return
        self.image_scale=scale;self.image_references=[]
        for index,original in self.image_sources.items():
            photo=original.subsample(scale);self.image_references.append(photo)
            self.image_labels[index].configure(image=photo,text='')

    def refresh_states(self):
        self.states.delete(*self.states.get_children())
        identity=self.reports.get('identity',UnavailableIdentification().identify().to_dict())
        package=self.reports.get('package',{})
        compatibility=LocalCalibrationProvider().compatibility(package,None).to_dict()
        unknown={'state':'desconocido','detail':'Sin datos; utiliza las acciones del lateral.'}
        source={'state':'confirmado' if 'files' in package else package.get('state','desconocido'),'detail':package.get('source','Ningún paquete importado')}
        rows=[('Identificación',identity),('Imágenes',self.reports.get('images',unknown)),('Procedencia',source),('Integridad MD5',package.get('integrity',package if package else unknown)),
              ('Compatibilidad',compatibility),('Captura',self.reports.get('capture',unknown)),
              ('Diagnóstico HMS',self.reports.get('diagnostic',unknown)),('Servidor',self.reports.get('server',unknown))]
        for title,data in rows:self.states.insert('', 'end',text=title,values=(data['state'],data['detail']))
