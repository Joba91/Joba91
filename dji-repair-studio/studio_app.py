"""Single-window DJI REPAIR Studio UI. All device operations use one worker."""
import io
import json
import queue
import threading
import time
from contextlib import redirect_stdout, redirect_stderr
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import comm_og_service_tool as backend
from studio_service import Session, validate, Cancelled, analyze, packet, unpack_hex
from studio_protocol import Client, MODULES, Decoder
from vision_view import VisionView
from vision_packages import inspect_package
from vision_protocol import analyze_capture
from vision_interfaces import UnavailableIdentification, LocalCalibrationProvider
from vision_services import AuthorizedServiceProvider, service_target

VERSION = '1.2.1'
MODELS = ('Mavic 3','Mavic 3 Pro','Mavic 3E','Mavic 3T','Mavic 3 Classic',
          'Mavic 3 Cine','Mavic 4 Pro','Mini 3 Pro','Mini 4 Pro','Mini 5 Pro')
PROFILE_CODES = {'Mavic 3':'WM260','Mavic 3 Cine':'WM260','Mavic 4 Pro':'MAVIC4PRO','Mini 5 Pro':'MT5MFND'}
CALIBRATION_ACTIONS = ('JointCoarse','LinearHall','Entrar modo fabrica','Salir modo fabrica','Escuchar progreso (20 s)')
VISION_ACTIONS = ('Importar carpeta visión','Importar ZIP visión','Analizar captura visión','Comprobar servidor visión','Identificación visión')

class ProgressState:
    """No time-based inference of motor/calibration completion."""
    def __init__(self): self.reset()
    def reset(self): self.value=0; self.mode='indeterminate'; self.label='Esperando respuesta'; self.failed=False; self.measured=False
    def update(self, event):
        if self.failed: return
        self.mode=event.get('mode','indeterminate')
        if self.mode=='determinate':
            self.measured=True; self.value=max(self.value,min(100,max(0,int(event.get('percent',0)))))
        self.label=event.get('label','')
    def finish(self, success, label):
        self.failed=not success
        self.mode='determinate'; self.label=label
        # Finishing a worker is not proof that a calibration finished.

class StreamWriter(io.TextIOBase):
    def __init__(self, emit): self.emit=emit; self.pending=''
    def write(self, text):
        self.pending+=text
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            if line:self.emit(line)
        return len(text)
    def flush(self):
        if self.pending:self.emit(self.pending);self.pending=''

class StudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'DJI REPAIR Studio {VERSION}')
        self.geometry(f'{min(1280,max(1000,self.winfo_screenwidth()-70))}x{min(850,max(650,self.winfo_screenheight()-90))}')
        self.minsize(1000,650)
        self.events=queue.Queue();self.stop=threading.Event();self.running=False;self.report=None
        self.progress_state=ProgressState();self.stage_history=[]
        self.model=tk.StringVar(value='Mavic 3');self.mode=tk.StringVar(value='bulk');self.port=tk.StringVar()
        self.baud=tk.StringVar(value='9600');self.timeout=tk.StringVar(value='2000');self.retries=tk.StringVar(value='3')
        self.firmware=tk.StringVar();self.prepared=tk.BooleanVar(value=False)
        self.status=tk.StringVar(value='Configura la conexión y elige una acción en el lateral.')
        self.progress_text=tk.StringVar(value='Sin operación — 0 %');self.progress_value=tk.DoubleVar(value=0)
        self.percent_text=tk.StringVar(value='0 %');self.connection_text=tk.StringVar(value='Sin consulta')
        self.ascii=tk.BooleanVar(value=False);self.filter_hex=tk.StringVar()
        self.fly_action=tk.StringVar(value='list');self.fly_start=tk.StringVar(value='0');self.fly_count=tk.StringVar(value='100')
        self.fly_name=tk.StringVar();self.fly_value=tk.StringVar();self.fly_alt=tk.BooleanVar(value=True)
        self.fly_unlock=tk.BooleanVar(value=False);self.fly_format=tk.StringVar(value='simple')
        self.camera_action=tk.StringVar(value='EncryptCheck');self.pairkey=tk.StringVar();self.force=tk.BooleanVar(value=False)
        self.legacy_gimbal=tk.StringVar(value='JointCoarse')
        self.generator_fields={};self.operation_buttons=[];self.operation_actions=[];self.config_controls=[]
        self._build_ui();self.refresh_ports()
        self.model.trace_add('write',self.model_changed)
        self.protocol('WM_DELETE_WINDOW',self.close_window)
        self.poll_id=self.after(80,self.poll)

    def _build_ui(self):
        style=ttk.Style(self)
        if 'clam' in style.theme_names():style.theme_use('clam')
        style.configure('Title.TLabel',font=('Segoe UI',17,'bold'))
        style.configure('Action.TButton',padding=(8,3),anchor='w',font=('Segoe UI',9))
        style.configure('Percent.TLabel',font=('Segoe UI',14,'bold'))
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        header=ttk.Frame(self,padding=(12,8));header.grid(row=0,column=0,sticky='ew')
        ttk.Label(header,text='DJI REPAIR Studio',style='Title.TLabel').grid(row=0,column=0,sticky='w',columnspan=2)
        ttk.Label(header,text=f'Versión {VERSION} · una sola interfaz').grid(row=0,column=2,columnspan=5,sticky='e')
        for c in (1,3,5):header.columnconfigure(c,weight=1)
        ttk.Label(header,text='Modelo seleccionado').grid(row=1,column=0,sticky='w',pady=(8,3))
        models=list(MODELS)+[p.name for p in backend.PRODUCT_CODE if p.name not in PROFILE_CODES.values()]
        w=ttk.Combobox(header,textvariable=self.model,values=models,state='readonly');w.grid(row=1,column=1,sticky='ew',padx=(6,16),pady=(8,3));self.config_controls.append((w,'readonly'))
        ttk.Label(header,text='Conexión').grid(row=1,column=2,sticky='w',pady=(8,3))
        modes=ttk.Frame(header);modes.grid(row=1,column=3,sticky='w',pady=(8,3))
        for label,value in [('USB bulk','bulk'),('Puerto serie','port')]:
            w=ttk.Radiobutton(modes,text=label,value=value,variable=self.mode);w.pack(side='left',padx=3);self.config_controls.append((w,'normal'))
        ttk.Label(header,text='Puerto').grid(row=1,column=4,pady=(8,3))
        self.port_combo=ttk.Combobox(header,textvariable=self.port,width=16);self.port_combo.grid(row=1,column=5,sticky='ew',padx=6,pady=(8,3));self.config_controls.append((self.port_combo,'normal'))
        self.refresh_button=ttk.Button(header,text='Actualizar puertos',command=self.refresh_ports);self.refresh_button.grid(row=1,column=6,pady=(8,3));self.config_controls.append((self.refresh_button,'normal'))
        options=ttk.Frame(header);options.grid(row=2,column=0,columnspan=7,sticky='ew',pady=4)
        for label,var,width in [('Baudrate',self.baud,9),('Espera (ms)',self.timeout,7),('Reintentos',self.retries,4)]:
            ttk.Label(options,text=label).pack(side='left',padx=(0,4));w=ttk.Entry(options,textvariable=var,width=width);w.pack(side='left',padx=(0,12));self.config_controls.append((w,'normal'))
        ttk.Label(options,textvariable=self.connection_text).pack(side='right')
        body=ttk.Frame(self,padding=(12,0));body.grid(row=1,column=0,sticky='nsew');body.columnconfigure(1,weight=1);body.rowconfigure(0,weight=1)
        sidebar=ttk.Frame(body,width=245);sidebar.grid(row=0,column=0,sticky='ns',padx=(0,10));sidebar.grid_propagate(False)
        sidebar.rowconfigure(0,weight=1);sidebar.columnconfigure(0,weight=1)
        canvas=tk.Canvas(sidebar,width=233,highlightthickness=0);canvas.grid(row=0,column=0,sticky='nsew')
        self.action_canvas=canvas
        scroll=ttk.Scrollbar(sidebar,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
        actions=ttk.Frame(canvas);window=canvas.create_window((0,0),window=actions,anchor='nw')
        self.action_frame=actions
        actions.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        groups=[('IDENTIFICACIÓN Y DIAGNÓSTICO',[('Identificar equipo','Identificar'),('Consultar módulos','Módulos'),('Diagnóstico orientado','Diagnóstico')]),
                ('CALIBRACIÓN DEL GIMBAL',[('JointCoarse','JointCoarse'),('LinearHall','LinearHall'),('Entrar en modo fábrica','Entrar modo fabrica'),('Salir del modo fábrica','Salir modo fabrica'),('Escuchar progreso · 20 s','Escuchar progreso (20 s)')]),
                ('OPERACIONES AVANZADAS',[('Ejecutar parámetros','Parámetros'),('Ejecutar cámara','Cámara'),('Calibración heredada','Gimbal heredado')]),
                ('HERRAMIENTAS SIN CONEXIÓN',[('Analizar paquete HEX','Analizar'),('Generar paquete','Generar'),('Convertir HEX a texto','Convertir')]),
                ('VISIÓN · MINI 4 PRO',[(name,name) for name in VISION_ACTIONS])]
        for heading,items in groups:
            label=ttk.Label(actions,text=heading,font=('Segoe UI',9,'bold'));label.pack(anchor='w',pady=(6,3))
            if heading=='VISIÓN · MINI 4 PRO':self.vision_action_heading=label
            for label,action in items:
                b=ttk.Button(actions,text=label,style='Action.TButton',command=lambda a=action:self.dispatch(a));b.pack(fill='x',pady=1);self.operation_buttons.append(b);self.operation_actions.append(action)
        bottom=ttk.Frame(sidebar);bottom.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(8,0))
        self.stop_button=ttk.Button(bottom,text='Detener lectura',command=self.stop.set,state='disabled');self.stop_button.pack(fill='x',pady=2)
        self.save_button=ttk.Button(bottom,text='Guardar informe',command=self.save_report,state='disabled');self.save_button.pack(fill='x',pady=2)
        ttk.Button(bottom,text='Limpiar registro',command=self.clear_log).pack(fill='x',pady=2)
        self.tabs=ttk.Notebook(body);self.tabs.grid(row=0,column=1,sticky='nsew')
        self.pages={}
        for name in ('Registro','Calibración','Parámetros','Cámara','Paquetes','Conversor'):
            page=ttk.Frame(self.tabs,padding=10);self.tabs.add(page,text=name);self.pages[name]=page
        self.vision=VisionView(self.tabs);self.tabs.add(self.vision,text='Visión Mini 4 Pro');self.pages['Visión Mini 4 Pro']=self.vision
        self.config_controls.extend(self.vision.controls)
        self.tabs.bind('<<NotebookTabChanged>>',self.reveal_actions)
        self._build_log();self._build_calibration();self._build_advanced();self._build_packets()
        progress=ttk.Frame(self,padding=(12,10));progress.grid(row=2,column=0,sticky='ew');progress.columnconfigure(0,weight=1)
        ttk.Label(progress,textvariable=self.progress_text).grid(row=0,column=0,sticky='w')
        ttk.Label(progress,textvariable=self.percent_text,style='Percent.TLabel').grid(row=0,column=1,rowspan=2,padx=(12,0))
        self.progress_bar=ttk.Progressbar(progress,maximum=100,variable=self.progress_value);self.progress_bar.grid(row=1,column=0,sticky='ew',pady=5)
        ttk.Label(progress,textvariable=self.status,wraplength=1100).grid(row=2,column=0,columnspan=2,sticky='w')

    def _build_log(self):
        page=self.pages['Registro'];page.columnconfigure(0,weight=1);page.rowconfigure(2,weight=1)
        self.results=ttk.Treeview(page,columns=('estado','hardware','version'),show='tree headings',height=4)
        for col,label,width in [('#0','Módulo',105),('estado','Respuesta',155),('hardware','Hardware informado',190),('version','Versión de módulo',125)]:
            self.results.heading(col,text=label);self.results.column(col,width=width,minwidth=70)
        self.results.grid(row=0,column=0,sticky='ew',pady=(0,8))
        controls=ttk.Frame(page);controls.grid(row=1,column=0,sticky='ew',pady=(0,6))
        ttk.Label(controls,text='Filtro HEX:').pack(side='left');ttk.Entry(controls,textvariable=self.filter_hex,width=22).pack(side='left',padx=6)
        ttk.Checkbutton(controls,text='Duplicar como texto ASCII',variable=self.ascii).pack(side='left')
        self.log=tk.Text(page,wrap='word',state='disabled',font=('Consolas',10));self.log.grid(row=2,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(page,orient='vertical',command=self.log.yview);scrollbar.grid(row=2,column=1,sticky='ns');self.log.configure(yscrollcommand=scrollbar.set)
        ttk.Label(page,text='El modelo es seleccionado manualmente. Una versión recibida no confirma el estado de salud.',wraplength=750).grid(row=3,column=0,sticky='w',pady=(8,0))

    def _entry(self,page,row,label,var,values=None):
        ttk.Label(page,text=label).grid(row=row,column=0,sticky='w',pady=5)
        w=ttk.Entry(page,textvariable=var) if values is None else ttk.Combobox(page,textvariable=var,values=values,state='readonly')
        w.grid(row=row,column=1,sticky='ew',padx=10,pady=5);self.config_controls.append((w,'normal' if values is None else 'readonly'))
        page.columnconfigure(1,weight=1);return w

    def _build_calibration(self):
        page=self.pages['Calibración'];self._entry(page,0,'Firmware de DJI Fly',self.firmware)
        w=ttk.Checkbutton(page,text='Ya entré en modo fábrica y reinicié el dron',variable=self.prepared);w.grid(row=1,column=0,columnspan=2,sticky='w',pady=8);self.config_controls.append((w,'normal'))
        text=('Secuencia: entrar en modo fábrica → reiniciar manualmente → marcar la casilla → calibrar → salir del modo fábrica → reiniciar.\n\n'
              'Las calibraciones son experimentales y pueden provocar errores 40011/40021. Retira las hélices y el protector y deja libre el recorrido.\n\n'
              'El porcentaje cuenta hitos de esta sesión; no mide tiempo restante ni avance físico continuo. Sin datos verificables se muestra «Esperando respuesta».\n\n'
              'Detener lectura no frena los motores. No se escriben coeficientes IMU fijos ni se promete eliminar el error 40021.\n\n'
              'Mavic 4 Pro y Classic conservan consultas de información; estas calibraciones no están validadas para ellos.')
        ttk.Label(page,text=text,wraplength=720,justify='left').grid(row=2,column=0,columnspan=2,sticky='nw',pady=12)
        self._entry(page,3,'Acción heredada (otros modelos)',self.legacy_gimbal,['JointCoarse','LinearHall'])
        ttk.Label(page,text='Usa los botones del lateral para ejecutar. La calibración heredada mantiene las restricciones del motor original.',wraplength=720).grid(row=4,column=0,columnspan=2,sticky='w',pady=12)

    def _build_advanced(self):
        page=self.pages['Parámetros']
        for row,(label,var,values) in enumerate([('Acción',self.fly_action,['list','get','set']),('Índice inicial',self.fly_start,None),('Cantidad',self.fly_count,None),('Nombre de parámetro',self.fly_name,None),('Valor',self.fly_value,None),('Formato',self.fly_format,['simple','1line','2line','tab','csv'])]):self._entry(page,row,label,var,values)
        for row,(label,var) in enumerate([('Método alternativo',self.fly_alt),('Habilitar escritura moderna',self.fly_unlock)],6):
            w=ttk.Checkbutton(page,text=label,variable=var);w.grid(row=row,column=0,columnspan=2,sticky='w',pady=6);self.config_controls.append((w,'normal'))
        ttk.Label(page,text='Selecciona la acción y ejecútala desde «Ejecutar parámetros», en el lateral.',wraplength=700).grid(row=8,column=0,columnspan=2,sticky='w',pady=10)
        page=self.pages['Cámara'];self._entry(page,0,'Acción heredada',self.camera_action,['EncryptCheck','EncryptPair']);self._entry(page,1,'Clave de emparejamiento HEX',self.pairkey)
        w=ttk.Checkbutton(page,text='Forzar escritura',variable=self.force);w.grid(row=2,column=0,columnspan=2,sticky='w',pady=8);self.config_controls.append((w,'normal'))
        ttk.Label(page,text='Son operaciones heredadas de comprobación/emparejamiento, no recuperación de imagen. Su disponibilidad depende del modelo y se valida en el motor original.',wraplength=700).grid(row=3,column=0,columnspan=2,sticky='w',pady=14)

    def _build_packets(self):
        page=self.pages['Paquetes'];page.columnconfigure(0,weight=1);page.columnconfigure(1,weight=1);page.rowconfigure(3,weight=1)
        ttk.Label(page,text='Paquete o captura HEX para analizar').grid(row=0,column=0,columnspan=2,sticky='w')
        self.hex=tk.Text(page,height=3,wrap='word',font=('Consolas',9));self.hex.grid(row=1,column=0,columnspan=2,sticky='ew',pady=6)
        self.hex.insert('1.0','55 0e 04 66 04 0a 8e ad 80 04 08 01 fb 95')
        params=ttk.LabelFrame(page,text='Generador sin conexión',padding=8);params.grid(row=2,column=0,columnspan=2,sticky='ew',pady=6)
        fields=[('Emisor HEX','0a'),('Receptor HEX','04'),('Secuencia decimal','0'),('Conjunto HEX','00'),('Comando HEX','01'),('Indicadores HEX','40'),('Contenido HEX','')]
        for index,(label,default) in enumerate(fields):
            row=index//2;col=index%2*2;var=tk.StringVar(value=default);self.generator_fields[label]=var
            ttk.Label(params,text=label).grid(row=row,column=col,sticky='w',padx=4,pady=3);ttk.Entry(params,textvariable=var,width=17).grid(row=row,column=col+1,sticky='ew',padx=4,pady=3)
        params.columnconfigure(1,weight=1);params.columnconfigure(3,weight=1)
        self.packet_output=tk.Text(page,height=7,wrap='word',font=('Consolas',10));self.packet_output.grid(row=3,column=0,columnspan=2,sticky='nsew',pady=6)
        ttk.Label(page,text='Analizar y generar no envía este contenido al dron. Ejecuta las herramientas desde el lateral.').grid(row=4,column=0,columnspan=2,sticky='w')
        page=self.pages['Conversor'];page.columnconfigure(0,weight=1);page.rowconfigure(3,weight=1)
        ttk.Label(page,text='Entrada HEX').grid(row=0,column=0,sticky='w');self.convert_hex=tk.Text(page,height=5);self.convert_hex.grid(row=1,column=0,sticky='ew',pady=8)
        ttk.Label(page,text='Texto ASCII').grid(row=2,column=0,sticky='w');self.convert_output=tk.Text(page,height=8);self.convert_output.grid(row=3,column=0,sticky='nsew',pady=8)

    def refresh_ports(self):
        try:
            from serial.tools.list_ports import comports
            values=[p.device for p in comports()];self.port_combo['values']=values
            if values and not self.port.get():self.port.set(values[0])
        except Exception as exc:self.status.set('No se pudieron enumerar los puertos: '+str(exc))

    def select_page(self,name):self.tabs.select(self.pages[name])
    def reveal_actions(self,event=None):
        if self.tabs.select()==str(self.vision):
            if not self.running and self.model.get()!='Mini 4 Pro':self.model.set('Mini 4 Pro')
            self.after(40,self.scroll_vision_actions)
    def scroll_vision_actions(self):
        if self.tabs.select()==str(self.vision):
            self.action_canvas.yview_moveto(self.vision_action_heading.winfo_y()/max(1,self.action_frame.winfo_height()))
    def append(self,text):
        if text.startswith(('TX ','RX ')):
            raw=bytes.fromhex(text[3:]);value=self.filter_hex.get().replace(' ','').lower()
            if text.startswith('RX ') and value and value not in raw.hex():return
            if self.ascii.get():text+=' | '+''.join(chr(c) if 32<=c<127 else '.' for c in raw)
        self.log.configure(state='normal');self.log.insert('end',text+'\n')
        if int(self.log.index('end-1c').split('.')[0])>5000:self.log.delete('1.0','1000.0')
        self.log.see('end');self.log.configure(state='disabled')
    def clear_log(self):
        self.log.configure(state='normal');self.log.delete('1.0','end');self.log.configure(state='disabled')

    def offline(self,action):
        try:
            if action=='Analizar':
                self.select_page('Paquetes');text=self.hex.get('1.0','end');raw=unpack_hex(text)
                decoder=Decoder();frames=decoder.feed(raw)
                result=analyze(text) if len(frames)==1 and frames[0]==raw else {'paquetes_validos':[analyze(f.hex()) for f in frames],'bytes_sin_paquete':len(decoder.buffer),'cabeceras_invalidas':decoder.invalid}
                output=json.dumps(result,ensure_ascii=False,indent=2);target=self.packet_output
            elif action=='Generar':
                self.select_page('Paquetes');v={k:var.get().strip() for k,var in self.generator_fields.items()}
                sequence=int(v['Secuencia decimal']);fields=[int(v[k],16) for k in ('Emisor HEX','Receptor HEX','Conjunto HEX','Comando HEX','Indicadores HEX')]
                if not 0<=sequence<=65535 or any(not 0<=x<=255 for x in fields):raise ValueError('Campos fuera de rango')
                data=unpack_hex(v['Contenido HEX']) if v['Contenido HEX'] else b''
                output=packet(fields[0],fields[1],sequence,fields[2],fields[3],data,fields[4]).hex(' ');target=self.packet_output
            else:
                self.select_page('Conversor');output=unpack_hex(self.convert_hex.get('1.0','end')).decode('ascii',errors='replace');target=self.convert_output
            target.delete('1.0','end');target.insert('1.0',output)
        except ValueError as exc:messagebox.showerror('Datos no válidos',str(exc),parent=self)

    def settings(self):
        baud=int(self.baud.get());timeout=int(self.timeout.get());retries=int(self.retries.get())
        if not 300<=baud<=3000000 or not 100<=timeout<=20000 or not 1<=retries<=10:raise ValueError('Baudrate, espera o reintentos fuera de rango')
        if self.mode.get()=='port' and not self.port.get().strip():raise ValueError('Selecciona un puerto serie')
        return SimpleNamespace(bulk=self.mode.get()=='bulk',port=self.port.get().strip(),baudrate=baud,timeout=min(timeout,200),total_timeout=timeout/1000,retry=retries,dry_test=False,verbose=1)

    def advanced_options(self,action,po):
        model=self.model.get();code=PROFILE_CODES.get(model,model)
        if code not in backend.PRODUCT_CODE.__members__:raise ValueError('Esta operación avanzada no está validada para ese modelo')
        if code=='MAVIC4PRO':raise ValueError('Para Mavic 4 Pro solo están habilitadas las consultas de información')
        po=SimpleNamespace(**vars(po));po.product=backend.PRODUCT_CODE.from_name(code)
        po.timeout=int(po.total_timeout*1000)
        if action=='Parámetros':
            po.svcmd=backend.SERVICE_CMD.FlycParam;po.subcmd=backend.FLYC_PARAM_CMD.from_name(self.fly_action.get().upper())
            po.fmt=self.fly_format.get();po.start=int(self.fly_start.get());po.count=int(self.fly_count.get());po.param_name=self.fly_name.get().strip();po.param_value=self.fly_value.get().strip();po.alt=self.fly_alt.get()
            po.allow_modern_set=po.allow_wm260_set=self.fly_unlock.get()
            if po.start<0 or not 1<=po.count<=10000:raise ValueError('Índice o cantidad no válidos')
            if po.subcmd!=backend.FLYC_PARAM_CMD.LIST and not po.param_name:raise ValueError('Escribe el nombre del parámetro')
            if po.subcmd==backend.FLYC_PARAM_CMD.SET and not po.param_value:raise ValueError('Escribe el valor del parámetro')
        elif action=='Cámara':
            po.svcmd=backend.SERVICE_CMD.CameraCalib;po.subcmd=backend.CAMERA_CALIB_CMD.from_name(self.camera_action.get().upper());po.force=self.force.get();value=self.pairkey.get().strip();po.pairkey=bytes.fromhex(value) if value else None
        else:
            if code=='WM260':raise ValueError('Usa JointCoarse o LinearHall del lateral para Mavic 3; no la rutina heredada')
            po.svcmd=backend.SERVICE_CMD.GimbalCalib;po.subcmd=backend.GIMBAL_CALIB_CMD.from_name(self.legacy_gimbal.get().upper())
        return po

    def dispatch(self,action):
        if self.running:return
        if action in VISION_ACTIONS:self.dispatch_vision(action);return
        if action in ('Analizar','Generar','Convertir'):self.offline(action);return
        if self.model.get()=='Mini 4 Pro':
            self.select_page('Visión Mini 4 Pro')
            messagebox.showinfo('Mini 4 Pro · sin comunicación activa','Usa el módulo de visión sin conexión. La lectura USB y todas las operaciones activas de este modelo están deshabilitadas hasta validar el protocolo y sus endpoints.',parent=self)
            return
        try:
            po=self.settings();options=None
            if action in CALIBRATION_ACTIONS:
                self.select_page('Calibración');validate(self.model.get(),self.firmware.get().strip(),action,self.prepared.get())
            elif action in ('Parámetros','Cámara','Gimbal heredado'):
                self.select_page({'Parámetros':'Parámetros','Cámara':'Cámara','Gimbal heredado':'Calibración'}[action]);options=self.advanced_options(action,po)
        except (ValueError,KeyError) as exc:messagebox.showerror('Configuración',str(exc),parent=self);return
        modifying=action in ('JointCoarse','LinearHall','Entrar modo fabrica','Salir modo fabrica','Gimbal heredado') or (action=='Parámetros' and self.fly_action.get()=='set') or (action=='Cámara' and self.camera_action.get()=='EncryptPair')
        if modifying:
            text=f'Acción: {action}\nModelo seleccionado: {self.model.get()}\n\n'
            if action in ('JointCoarse','LinearHall','Gimbal heredado'):
                text+='El gimbal se moverá. Retira las hélices y el protector y deja libre su recorrido. Esta calibración experimental puede provocar errores 40011/40021.\n\n'
            elif action in ('Entrar modo fabrica','Salir modo fabrica'):text+='Requiere reiniciar manualmente el equipo después de la confirmación.\n\n'
            else:text+='Esta operación puede escribir datos. Verifica los valores y conserva un respaldo.\n\n'
            if not messagebox.askyesno('Confirmar operación',text+'¿Continuar?',parent=self):return
        self.running=True;self.stop.clear();self.progress_state.reset();self.stage_history=[]
        self.report={'herramienta':'DJI REPAIR Studio','version':VERSION,'modelo_declarado':self.model.get(),'firmware_declarado':self.firmware.get().strip(),'accion':action,'fecha_unix':time.time(),'resultado':None,'paquetes':[],'progreso':[]}
        self._set_busy(True,action not in ('Parámetros','Cámara','Gimbal heredado'))
        self.progress_bar.configure(mode='indeterminate');self.progress_value.set(0);self.progress_bar.start(12);self.percent_text.set('—');self.progress_text.set('Esperando respuesta; sin porcentaje confirmado')
        self.status.set('Ejecutando: '+action);self.append('>>> '+action+' · '+self.model.get())
        if action in ('Identificar','Módulos','Diagnóstico'):self.select_page('Registro')
        threading.Thread(target=self.worker,args=(action,po,options),daemon=True).start()

    def dispatch_vision(self,action):
        self.select_page('Visión Mini 4 Pro')
        self.model.set('Mini 4 Pro')
        snapshot={'format':self.vision.format.get()}
        try:
            if action=='Importar carpeta visión':
                snapshot['path']=filedialog.askdirectory(parent=self,title='Paquete local de visión (solo lectura)')
            elif action in ('Importar ZIP visión','Analizar captura visión'):
                snapshot['path']=filedialog.askopenfilename(parent=self,title=action,
                    filetypes=[('ZIP','*.zip')] if action=='Importar ZIP visión' else [('Registros y capturas','*.log *.txt *.bin *.raw *.dump'),('Todos','*.*')])
            elif action=='Comprobar servidor visión':
                snapshot['url']=self.vision.url.get().strip();service_target(snapshot['url'])
                snapshot['timeout']=float(self.vision.timeout.get())
            if 'path' in snapshot and not snapshot['path']:return
        except ValueError as exc:messagebox.showerror('Configuración de visión',str(exc),parent=self);return
        self.running=True;self.stop.clear();self.progress_state.reset()
        self.report={'herramienta':'DJI REPAIR Studio','version':VERSION,'accion':action,'modelo_declarado':'Mini 4 Pro',
                     'fecha_unix':time.time(),'resultado':None,'paquetes':[],'progreso':[],'vision':dict(self.vision.reports)}
        self._set_busy(True,action!='Comprobar servidor visión')
        self.progress_bar.configure(mode='indeterminate');self.progress_value.set(0);self.progress_bar.start(12)
        self.percent_text.set('—');self.progress_text.set('Procesando diagnóstico de visión; sin comunicación con el dron')
        self.status.set(action);self.append('>>> '+action)
        threading.Thread(target=self.vision_worker,args=(action,snapshot),daemon=True).start()

    def vision_worker(self,action,snapshot):
        try:
            if action in ('Importar carpeta visión','Importar ZIP visión'):
                data=inspect_package(snapshot['path'],progress=lambda e:self.events.put(('progress',e)),cancelled=self.stop.is_set)
                data['candidates']=LocalCalibrationProvider().candidates(data)
                data['compatibility']=LocalCalibrationProvider().compatibility(data,None).to_dict();category='package'
                state=data['integrity']['state'];detail=f"Inventario: {data['file_count']} archivos; integridad {state}. Compatibilidad no demostrada."
            elif action=='Analizar captura visión':
                data=analyze_capture(snapshot['path'],snapshot['format'],self.stop.is_set);category='capture'
                state=data['state'];detail=f"Captura: {data['valid_frames']} tramas válidas, {data['issue_count']} incidencias; identidad desconocida."
            elif action=='Comprobar servidor visión':
                data=AuthorizedServiceProvider(snapshot['url']).probe(snapshot['timeout']);category='server'
                state=data['state'];detail=data['detail']
            else:
                data=UnavailableIdentification().identify().to_dict();category='identity';state=data['state'];detail=data['detail']
            self.events.put(('vision',{'category':category,'data':data}))
            self.events.put(('error' if state=='error' else 'result',{'estado':state,'detalle':detail}))
        except Exception as exc:
            category='package' if action.startswith('Importar') else 'capture' if action=='Analizar captura visión' else 'server' if action=='Comprobar servidor visión' else 'identity'
            data={'state':'error','detail':str(exc),'source':'Operación local o sondeo solicitado'}
            self.events.put(('vision',{'category':category,'data':data}))
            self.events.put(('error',{'estado':'error','detalle':str(exc)}))
        finally:self.events.put(('done',None))

    def _set_busy(self,busy,cancellable=True):
        self.sync_operation_buttons(busy)
        for control,state in self.config_controls:control.configure(state='disabled' if busy else state)
        self.stop_button.configure(state='normal' if busy and cancellable else 'disabled');self.save_button.configure(state='disabled' if busy or self.report is None else 'normal')

    def sync_operation_buttons(self,busy):
        for button,action in zip(self.operation_buttons,self.operation_actions):
            blocked=self.model.get()=='Mini 4 Pro' and action not in VISION_ACTIONS+('Analizar','Generar','Convertir')
            button.configure(state='disabled' if busy or blocked else 'normal')

    def model_changed(self,*args):
        self.sync_operation_buttons(self.running)
        self.connection_text.set('Mini 4 Pro: USB de visión no habilitado' if self.model.get()=='Mini 4 Pro' else 'Consulta pendiente para el modelo seleccionado')
        if self.model.get()=='Mini 4 Pro' and not self.running:self.select_page('Visión Mini 4 Pro')

    def worker(self,action,po,advanced=None):
        transport=None;session=None;client=None
        emit=lambda text:self.events.put(('log',text))
        progress=lambda event:self.events.put(('progress',event))
        try:
            if advanced is not None:
                result=self.run_advanced(action,advanced,emit)
            else:
                transport=backend.open_serial_port(po)
                if not po.bulk:transport.timeout=0.1
                if action in ('Identificar','Módulos','Diagnóstico'):
                    class Adapter:
                        def read(inner):return transport.read(4096)
                        def write(inner,data):return transport.write(data)
                    client=Client(Adapter(),timeout=po.total_timeout,retries=po.retry,cancelled=self.stop.is_set,emit=emit)
                    targets=['Controlador'] if action=='Identificar' else list(MODULES)
                    rows=[]
                    for index,name in enumerate(targets):
                        row=client.query(name);rows.append(row);self.events.put(('module',row))
                        progress({'percent':int((index+1)/len(targets)*100),'mode':'determinate','basis':'consultas','label':f'Consultas completadas: {index+1}/{len(targets)}'})
                    count=sum(row['estado']=='version_recibida' for row in rows)
                    if not count:raise ConnectionError('Ningún módulo devolvió una versión reconocible')
                    if action=='Diagnóstico':emit('Los códigos 40021 y 1D020001 son referencias de diagnóstico, no errores detectados automáticamente. Una consulta de versiones no prueba la salud del equipo.')
                    result={'estado':'consulta_completada','detalle':f'{count}/{len(rows)} módulos con versión reconocible; revisa las respuestas individuales.','modulos':rows}
                else:
                    session=Session(transport,emit=emit,cancelled=self.stop.is_set,timeout=po.total_timeout,progress=progress)
                    if action=='Entrar modo fabrica':result=session.factory(True)
                    elif action=='Salir modo fabrica':result=session.factory(False)
                    elif action in ('JointCoarse','LinearHall'):result=session.calibrate(action)
                    else:result=session.monitor(20)
            self.events.put(('result',result))
        except (Cancelled,InterruptedError) as exc:self.events.put(('error',{'estado':'lectura_detenida','detalle':str(exc)}))
        except Exception as exc:self.events.put(('error',{'estado':'fallo_o_no_confirmado','detalle':str(exc)}))
        finally:
            if session:self.events.put(('packets',session.events))
            if client:self.events.put(('packets',client.packets))
            if transport:
                try:transport.close()
                except Exception as exc:self.events.put(('log','Error al cerrar conexión: '+str(exc)))
            self.events.put(('done',None))

    def run_advanced(self,action,po,emit):
        opened=[];original=backend.open_serial_port
        def opener(options):
            connection=original(options);opened.append(connection);return connection
        backend.open_serial_port=opener
        writer=StreamWriter(emit)
        try:
            with redirect_stdout(writer),redirect_stderr(writer):
                if action=='Parámetros':backend.do_flyc_param_request(po)
                elif action=='Cámara':backend.do_camera_calib_request(po)
                else:backend.do_gimbal_calib_request(po)
            return {'estado':'comando_finalizado','detalle':'El motor de servicio terminó; revisa el registro. No hay porcentaje de esta operación disponible.'}
        finally:
            writer.flush();backend.open_serial_port=original
            for connection in opened:
                try:connection.close()
                except Exception:pass

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='log':self.append(data)
                elif kind=='vision':
                    self.vision.apply_report(data['category'],data['data']);self.report['vision']=dict(self.vision.reports)
                elif kind=='progress':
                    self.report['progreso'].append(data);self.progress_state.update(data);self.render_progress()
                elif kind=='module':
                    self.results.insert('', 'end',text=data['modulo'],values=(data['estado'],data.get('hardware','—'),data.get('firmware_modulo','—')))
                elif kind in ('result','error'):
                    self.report['resultado']=data;self.progress_state.finish(kind=='result',data['detalle']);self.status.set(data['detalle']);self.append(json.dumps(data,ensure_ascii=False,indent=2))
                    if self.report['accion'] in ('Identificar','Módulos','Diagnóstico'):self.connection_text.set(data['estado'])
                elif kind=='packets':self.report['paquetes']=data
                elif kind=='done':
                    self.running=False;self.progress_bar.stop();self._set_busy(False);self.render_progress()
                    if self.report['accion'] in ('Entrar modo fabrica','Salir modo fabrica'):self.prepared.set(False)
        except queue.Empty:pass
        self.poll_id=self.after(80,self.poll)

    def render_progress(self):
        state=self.progress_state
        if state.mode=='determinate':
            self.progress_bar.stop();self.progress_bar.configure(mode='determinate');self.progress_value.set(state.value)
            self.percent_text.set(f'{state.value} %' if state.measured else '—')
        else:self.percent_text.set('—')
        self.progress_text.set(state.label)
        if state.failed:self.percent_text.set(f'{state.value} % · no confirmado' if state.measured else 'Sin confirmar')

    def save_report(self):
        if self.running or self.report is None:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',initialfile='DJI-REPAIR-informe.json',filetypes=[('Informe JSON','*.json')])
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f:json.dump(self.report,f,ensure_ascii=False,indent=2)
            except OSError as exc:messagebox.showerror('No se pudo guardar',str(exc),parent=self)

    def close_window(self):
        if self.running:messagebox.showinfo('Operación en curso','Espera a que termine la operación. Detener lectura no frena el gimbal.',parent=self);return
        self.after_cancel(self.poll_id);self.destroy()
