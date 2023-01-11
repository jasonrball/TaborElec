import os
import sys
import math
srcpath = os.path.realpath('SourceFiles')
sys.path.append(srcpath)
import pyte_visa_utils as pyte
from tevisainst import TEVisaInst
from teproteus import TEProteusAdmin as TepAdmin

import numpy as np
from numpy.fft import fft, fftshift
import time
import ipywidgets as widgets
from IPython.core.debugger import set_trace
from scipy.signal import chirp, sweep_poly, windows
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons, CheckButtons
import keyboard

#Init
breakVal = 0
dcOff = 50
spectrumInv = 0

#Set rates for DAC and ADC
sampleRateDAC = 2.2E9
sampleRateADC = (sampleRateDAC * 32) / 20 # This ratio is required for clock sync

#Set number of frames to be collected
numframes, framelen = 1, 4800
totlen = numframes * framelen

#Preallocate
wav1 = np.zeros(framelen, dtype=np.uint16)
fftPlot = np.zeros(int(framelen/2), dtype=np.uint16)
xT = np.linspace(0, numframes * framelen,  numframes * framelen )
xT =  xT/sampleRateADC
dacWaveI = []
dacWaveQ = []

# Connect to instrument(PXI)
sid = 4 #PXI slot of AWT on chassis
admin = TepAdmin() #required to control PXI module
inst = admin.open_instrument(slot_id=sid) 

resp = inst.send_scpi_query("*IDN?") # Get the instrument's *IDN
print('connected to: ' + resp) # Print *IDN


# initializations .. 

inst.send_scpi_cmd('*CLS; *RST')

#AWG channel 1
inst.send_scpi_cmd(':INST:CHAN 1')

print('CH I DAC Clk Freq {0}'.format(sampleRateDAC))
cmd = ':FREQ:RAST {0}'.format(sampleRateDAC)
inst.send_scpi_cmd(cmd)
inst.send_scpi_cmd(':INIT:CONT ON')
inst.send_scpi_cmd(':TRAC:DEL:ALL')

#AWG channel 2
inst.send_scpi_cmd(':INST:CHAN 2')

print('CH Q DAC Clk Freq {0}'.format(sampleRateDAC))
cmd = ':FREQ:RAST {0}'.format(sampleRateDAC)
inst.send_scpi_cmd(cmd)
inst.send_scpi_cmd(':INIT:CONT ON')
inst.send_scpi_cmd(':TRAC:DEL:ALL')

# Setup the digitizer 

inst.send_scpi_cmd(':DIG:MODE SING')

print('ADC Clk Freq {0}'.format(sampleRateADC))
cmd = ':DIG:FREQ  {0}'.format(sampleRateADC)
inst.send_scpi_cmd(cmd)

# Enable capturing data from channel 1
inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB')
# Select the internal-trigger as start-capturing trigger:
inst.send_scpi_cmd(':DIG:TRIG:SOURCE CPU')

cmd = ':DIG:ACQuire:FRAM:DEF {0},{1}'.format(numframes, framelen)
inst.send_scpi_cmd(cmd)

# Select the frames for the capturing 
# (all the four frames in this example)
capture_first, capture_count = 1, numframes
cmd = ':DIG:ACQuire:FRAM:CAPT {0},{1}'.format(capture_first, capture_count)
inst.send_scpi_cmd(cmd)

# Start the digitizer's capturing machine
inst.send_scpi_cmd(':DIG:INIT ON')
inst.send_scpi_cmd(':DIG:TRIG:IMM')
inst.send_scpi_cmd(':DIG:INIT OFF')

# Choose which frames to read (all in this example)
inst.send_scpi_cmd(':DIG:DATA:SEL ALL')

# Choose what to read 
# (only the frame-data without the header in this example)
inst.send_scpi_cmd(':DIG:DATA:TYPE FRAM')

# Get the total data size (in bytes)
resp = inst.send_scpi_query(':DIG:DATA:SIZE?')
num_bytes = np.uint32(resp)
print('Total read size in bytes: ' + resp)
print()

# Read the data that was captured by channel 1:
inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
wavlen = num_bytes // 2
rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)

fourierTransform = np.fft.fft(wav1-dcOff)/len(wav1)           # Normalize amplitude
fourierTransform = abs(fourierTransform[range(int(len(wav1)/2))]) # Exclude sampling frequency

tpCount     = len(wav1)
timeStep  = xT[1]-xT[0]
xF = np.fft.fftfreq(tpCount, timeStep)
xF = xF[range(int(len(wav1)/2))]

if(spectrumInv == 1):
    fftPlot = np.log10(fourierTransform[::-1])
else:
    fftPlot = np.log10(fourierTransform)
  
def vMax(val):
    global inst
    cmd = ':DIG:CHAN:RANG HIGH'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:CHAN:RANG?')
    print('Range ' + range)
    
def vMed(val):
    cmd = ':DIG:CHAN:RANG MED'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:CHAN:RANG?')
    print('Range ' + range)

def vMin(val):
    cmd = ':DIG:CHAN:RANG LOW'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:CHAN:RANG?')
    print('Range ' + range)
    
def freeRun(val):
    cmd = ':DIG:TRIG:SOURCE CPU'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:TRIG:SOURCE?')
    print('Trigger ' + range)
    
def trigExt(val):
    cmd = ':DIG:TRIG:SOURCE TASK1'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:TRIG:SOURCE?')
    print('Trigger ' + range)    
 
def dc(val):
    ax2.set_xticklabels(['', '0Hz', '562MHz', '1124MHz', '1686MHz', '2248MHz', '2810MHz'])
    global spectrumInv
    spectrumInv = 0; 

def two(val):
    ax2.set_xticklabels(['', '2700MHz', '3268MHz', '3824MHz', '4386MHz', '4948MHz', '5510MHz'])
    global spectrumInv
    spectrumInv = 1;

def five(val):
    ax2.set_xticklabels(['', '5400MHz', '5962MHz', '6524MHz', '7086MHz', '7648MHz', '8210MHz'])
    global spectrumInv
    spectrumInv = 0;

def eight(val):
    ax2.set_xticklabels(['', '8100MHz', '8662MHz', '9225MHz', '9787MHz', '10350MHz', '10910MHz'])
    global spectrumInv
    spectrumInv = 1;
    
def exitLoop(val):
    global breakVal
    breakVal = 1


# Run GUI event loop
plt.ion()
  
# Create sub plots
figure, ax1 = plt.subplots(2)
line1, = ax1[0].plot(xT, wav1-dcOff, color="yellow")
line2, = ax1[1].plot(xF, fftPlot, color="yellow")

# setting x-axis label and y-axis label
ax1[0].set(xlabel='Time = (Pts/'+ str(sampleRateDAC)+')', ylabel='Amplitude = (ADCRng/4096)')
ax1[0].set_position([0.2, 0.55, 0.7, 0.35]) #x, y, w, h]
ax1[0].set_ylim([0,4096])
ax1[0].set(facecolor = "black")
ax1[0].grid()

ax1[1].set(xlabel='Frequency', ylabel='FFT Amplitude')
ax1[1].set_position([0.2, 0.1, 0.7, 0.35]) #x, y, w, h]
ax1[1].set_ylim([0,1000])
ax1[1].set_xlim([0,60e6])
ax1[1].set(facecolor = "black")
ax1[1].grid()

xAnchor = 0.04
yAnchor = 0.33

ax1_button_500 = plt.axes([xAnchor, 0.85 , 0.03,0.05]) #xposition, yposition, width and height
grid_button_500 = Button(ax1_button_500, 'Max', color = 'white', hovercolor = 'grey')
grid_button_500.on_clicked(vMax)

ax1_button_800 = plt.axes([xAnchor+0.035, 0.85 , 0.03,0.05]) #xposition, yposition, width and height
grid_button_800 = Button(ax1_button_800, 'Med', color = 'white', hovercolor = 'grey')
grid_button_800.on_clicked(vMed)

ax1_button_1000 = plt.axes([xAnchor+(0.035*2), 0.85 , 0.03,0.05]) #xposition, yposition, width and height
grid_button_1000 = Button(ax1_button_1000, 'Min', color = 'white', hovercolor = 'grey')
grid_button_1000.on_clicked(vMin)


yAnchor = 0.7
ax3_button_free = plt.axes([0.04, yAnchor , 0.1,0.05]) #xposition, yposition, width and height
grid_button_free = Button(ax3_button_free, 'Free Run', color = 'white', hovercolor = 'grey')
grid_button_free.on_clicked(freeRun)

ax3_button_trig = plt.axes([0.04, yAnchor-0.075 , 0.1,0.05]) #xposition, yposition, width and height
grid_button_trig = Button(ax3_button_trig, 'Trigger', color = 'white', hovercolor = 'grey')
grid_button_trig.on_clicked(trigExt)

ax3_button_exit = plt.axes([0.04, yAnchor-(0.075*3) , 0.1,0.05]) #xposition, yposition, width and height
grid_button_exit = Button(ax3_button_exit, 'Exit', color = 'white', hovercolor = 'grey')
grid_button_exit.on_clicked(exitLoop)

def makeSineData():
    global dacWaveI
    global dacWaveQ
    
    ampI = 1  
    ampQ = 1
    max_dac=65535
    half_dac=max_dac/2
    data_type = np.uint16
    
    #Set waveform length
    segLen = 1024 # Signal
    
    cycles = 10
    time = np.linspace(0, segLen-1, segLen)
    omega = 2 * np.pi * cycles
    dacWave = ampI*np.cos(omega*time/segLen)
    
    print('Frequency {0} Hz'.format(sampleRateDAC*cycles/segLen))
   
    dacWaveI = ((dacWave) + 1.0) * half_dac  
    dacWaveI = dacWaveI.astype(data_type)
    
    dacWave = ampQ*np.sin(omega*time/segLen)  
    
    dacWaveQ = ((dacWave) + 1.0) * half_dac  
    
    dacWaveQ = dacWaveQ.astype(data_type)
    
def makePulseData():
    global dacWaveI
    global dacWaveQ
    
    ampI = 1  
    ampQ = 1  
    max_dac=65535
    half_dac=max_dac/2
    data_type = np.uint16
    
    #Set waveform length
    segLen = 1024 # Signal
    segLenDC = 1024 #DC
    
    cycles = 10
    time = np.linspace(0, segLen-1, segLen)
    omega = 2 * np.pi * cycles
    dacWave = ampI*np.cos(omega*time/segLen)
   
    dacWaveI = ((dacWave) + 1.0) * half_dac  
    dacWaveI = dacWaveI.astype(data_type)
    
    #Set DC
    dacWaveDC = np.zeros(segLenDC)       
    dacWaveDC = dacWaveDC+(max_dac//2)
    dacWaveDC = dacWaveDC.astype(np.uint16)
    
    dacWaveI = np.concatenate([dacWaveI, dacWaveDC])
    
    dacWave = ampQ*np.sin(omega*time/segLen)  
    
    dacWaveQ = ((dacWave) + 1.0) * half_dac  
    
    dacWaveQ = dacWaveQ.astype(data_type)
    
    dacWaveQ = np.concatenate([dacWaveQ, dacWaveDC])
    
def makeGaussPulseData():
    global dacWaveI
    global dacWaveQ
    
    ampI = 1  
    ampQ = 1 
    max_dac=65535
    half_dac=max_dac/2
    data_type = np.uint16
    
    #Set waveform length
    segLen = 1024 # Signal
    segLenDC = 1024 #DC
    
    cycles = 10
    time = np.linspace(0, segLen-1, segLen)
    omega = 2 * np.pi * cycles
    dacWave = ampI*np.cos(omega*time/segLen)
   
    timeGuassian = np.linspace(-(segLen)/2, (segLen)/2, segLen)
    variance=np.power(20, 2.) 
    modWave = (np.exp(-np.power((omega*timeGuassian/segLen), 2.) / (2 * variance)))

    dacWaveI = ((dacWave * modWave) + 1.0) * half_dac  
    dacWaveI = dacWaveI.astype(data_type)
    
    #Set DC
    dacWaveDC = np.zeros(segLenDC)       
    dacWaveDC = dacWaveDC+(max_dac//2)
    dacWaveDC = dacWaveDC.astype(np.uint16)
    
    dacWaveI = np.concatenate([dacWaveI, dacWaveDC])
    
    dacWave = ampQ*np.sin(omega*time/segLen)  
    
    dacWaveQ = ((dacWave * modWave) + 1.0) * half_dac  
    
    dacWaveQ = dacWaveQ.astype(data_type)
    
    dacWaveQ = np.concatenate([dacWaveQ, dacWaveDC])


def downLoad_IQ_DUC_low():
    global dacWaveI
    global dacWaveQ
    
    
    dacWaveIQ = dacWaveI
    
    ch=1
    segnum = 1
    
    # Select channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    # Define segment
    cmd = ':TRAC:DEF {0}, {1}'.format(segnum, len(dacWaveIQ))
    inst.send_scpi_cmd(cmd)

    # Select the segment
    cmd = ':TRAC:SEL {0}'.format(segnum)
    inst.send_scpi_cmd(cmd)

    # Increase the timeout before writing binary-data:
    inst.timeout = 30000
    # Send the binary-data with *OPC? added to the beginning of its prefix.
    inst.write_binary_data('*OPC?; :TRAC:DATA', dacWaveIQ)
    # Set normal timeout
    inst.timeout = 10000

    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    

    cmd = ':OUTP ON'
    inst.send_scpi_cmd(cmd)


def downLoad_IQ_DUC_high():
    global dacWaveI
    global dacWaveQ
    
    arr_tuple = (dacWaveI, dacWaveQ)
    dacWaveIQ = np.vstack(arr_tuple).reshape((-1,), order='F')
    
    
    ch=1
    segnum = 1

    # Select channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    # Define segment
    cmd = ':TRAC:DEF {0}, {1}'.format(segnum, len(dacWaveIQ))
    inst.send_scpi_cmd(cmd)

    # Select the segment
    cmd = ':TRAC:SEL {0}'.format(segnum)
    inst.send_scpi_cmd(cmd)

    # Increase the timeout before writing binary-data:
    inst.timeout = 30000
    # Send the binary-data with *OPC? added to the beginning of its prefix.
    inst.write_binary_data('*OPC?; :TRAC:DATA', dacWaveIQ)
    # Set normal timeout
    inst.timeout = 10000

    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    
    # cmd = ':SOUR:INT x4'
    # #cmd = ':SOUR:INT x8'
    # rc = inst.send_scpi_cmd(cmd)

    # sampleRateDAC = 8E8
    # print('Sample Clk Freq {0}'.format(sampleRateDAC))
    # cmd = ':FREQ:RAST {0}'.format(sampleRateDAC)
    # rc = inst.send_scpi_cmd(cmd)

    cmd = ':SOUR:MODE DUC'
    rc = inst.send_scpi_cmd(cmd)

    cmd = ':SOUR:IQM ONE'
    rc = inst.send_scpi_cmd(cmd)

    cmd = ':SOUR:NCO:CFR1 1E9'
    rc = inst.send_scpi_cmd(cmd)

    cmd = ':SOUR:SIXD OFF'
    rc = inst.send_scpi_cmd(cmd)

    cmd = ':OUTP ON'
    inst.send_scpi_cmd(cmd)

def downLoad_I():
    global dacWaveI
    
    ch=1
    segnum = 1

    # Select channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    # Define segment
    cmd = ':TRAC:DEF {0}, {1}'.format(segnum, len(dacWaveI))
    inst.send_scpi_cmd(cmd)

    # Select the segment
    cmd = ':TRAC:SEL {0}'.format(segnum)
    inst.send_scpi_cmd(cmd)

    # Increase the timeout before writing binary-data:
    inst.timeout = 30000
    # Send the binary-data with *OPC? added to the beginning of its prefix.
    inst.write_binary_data('*OPC?; :TRAC:DATA', dacWaveI)
    # Set normal timeout
    inst.timeout = 10000

    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)

    cmd = ':OUTP ON'
    inst.send_scpi_cmd(cmd)

def downLoad_Q():
    global dacWaveQ
    
    ch=2
    segnum = 2

    # Select channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    # Define segment
    cmd = ':TRAC:DEF {0}, {1}'.format(segnum, len(dacWaveQ))
    inst.send_scpi_cmd(cmd)

    # Select the segment
    cmd = ':TRAC:SEL {0}'.format(segnum)
    inst.send_scpi_cmd(cmd)

    # Increase the timeout before writing binary-data:
    inst.timeout = 30000
    # Send the binary-data with *OPC? added to the beginning of its prefix.
    inst.write_binary_data('*OPC?; :TRAC:DATA', dacWaveQ)
    # Set normal timeout
    inst.timeout = 10000

    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    
    cmd = ':OUTP ON'
    inst.send_scpi_cmd(cmd)
    
def setTaskIQ():
   
    ch=1
    # I channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    cmd = ':TASK:COMP:LENG 1'
    inst.send_scpi_cmd(cmd)
     
    cmd = ':TASK:COMP:SEL 1' 
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:SEGM 1'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:DTR ON'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:NEXT1 1'
    inst.send_scpi_cmd(cmd)
    
    cmd = ':TASK:COMP:WRITE'
    inst.send_scpi_cmd(cmd)
    cmd = ':SOUR:FUNC:MODE TASK'
    inst.send_scpi_cmd(cmd)
    
    ch=2
    # Q channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    cmd = ':TASK:COMP:LENG 1'
    inst.send_scpi_cmd(cmd)
     
    cmd = ':TASK:COMP:SEL 1' 
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:SEGM 2'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:DTR ON'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:NEXT1 2'
    inst.send_scpi_cmd(cmd)
    
    cmd = ':TASK:COMP:WRITE'
    inst.send_scpi_cmd(cmd)
    cmd = ':SOUR:FUNC:MODE TASK'
    inst.send_scpi_cmd(cmd)  
    

def setTaskDUC():
   
    ch=1
    #Direct RF Output CH
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    cmd = ':TASK:COMP:LENG 1'
    inst.send_scpi_cmd(cmd)
     
    cmd = ':TASK:COMP:SEL 1' 
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:SEGM 1'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:DTR ON'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:NEXT1 1'
    inst.send_scpi_cmd(cmd)
    
    cmd = ':TASK:COMP:WRITE'
    inst.send_scpi_cmd(cmd)
    cmd = ':SOUR:FUNC:MODE TASK'
    inst.send_scpi_cmd(cmd)
           
    
def acquireData():
    wav1 = np.zeros(framelen, dtype=np.uint16)
    wavFFT = np.zeros(framelen, dtype=np.uint16)
    
    # Start the digitizer's capturing machine
    inst.send_scpi_cmd(':DIG:INIT ON')
    inst.send_scpi_cmd(':DIG:TRIG:IMM')
    # Stop the digitizer's capturing machine (to be on the safe side)
    inst.send_scpi_cmd(':DIG:INIT OFF')

    # Read the data that was captured by channel 1:
    inst.send_scpi_cmd(':DIG:CHAN:SEL 1')

    rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)
    wav1 = wav1-dcOff
    w = np.blackman(len(wav1))
    wavFFT = w * wav1
    #wavFFT = wav1
    fourierTransform = np.fft.fft(wavFFT)/len(wav1)           # Normalize amplitude
    fourierTransform = abs(fourierTransform[range(int(len(wav1)/2))]) # Exclude sampling frequency
    tpCount     = len(wav1)
    timeStep  = xT[1]-xT[0]
    xF = np.fft.fftfreq(tpCount, timeStep) 
    xF = xF[range(int(len(wav1)/2))]
    if(spectrumInv == 1):
        fftPlot = np.log10(fourierTransform[::-1])
    else:
        fftPlot = np.log10(fourierTransform)

    
    # Plot the samples
    # updating data values
    line1.set_xdata(xT)
    line1.set_ydata(wav1-dcOff) #Subtracting offset twice? 
    line2.set_xdata(xF)
    line2.set_ydata(fourierTransform)
    
    # drawing updated values
    figure.canvas.draw()
  
    # This will run the GUI event
    # loop until all UI events
    # currently waiting have been processed
    figure.canvas.flush_events()
     
    time.sleep(0.1)
    del wav1
    del fftPlot


#makeSineData()
makePulseData()
#makeGaussPulseData()

# -------- Low Band ----------
#downLoad_IQ_DUC_low()
#setTaskDUC()

# -------- High Band ----------
downLoad_IQ_DUC_high()
setTaskDUC()

# -------- Two-channel IQ ----------
#downLoad_I()
#downLoad_Q()
#setTaskIQ()

while True:
    try:
        if keyboard.is_pressed(' '):
            print("Stop initiated...")
            break
        if(breakVal==1):
            print("Stop initiated...")
            break
    
        acquireData()    
        
    except:
        break

inst.close_instrument()