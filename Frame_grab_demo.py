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


###########################################################################
# BY J. BALL, 2023/1/10-2023/1/11
#
# THIS PROGRAM DOES THE FOLLOWING:
#   - GENERATES LOW-BAND (FEW-MHZ PULSE)
#   - WRITES PULSE TO CHANNEL 1 OF TABOR PROTEUS AWT
#   - SETS UP TASK TABLE TO REPEAT PULSE INDEFINITELY WHILE TRIGGERING DIG EACH TIME
#   - SETS UP DIG TO COLLECT A CERTAIN NUMBER OF FRAMES WITH EACH ACQUISITION
#   - READS THE DATA FROM THE INSTRUMENT
#
###########################################################################


#Init
breakVal = 0
dcOff = 50
spectrumInv = 0

#Set rates for DAC and ADC
sampleRateDAC = 2.2E9
sampleRateADC = (sampleRateDAC * 32) / 20 # This ratio is required for clock sync


# Connect to instrument(PXI)
sid = 4 #PXI slot of AWT on chassis
admin = TepAdmin() #required to control PXI module
inst = admin.open_instrument(slot_id=sid) 

resp = inst.send_scpi_query("*IDN?") # Get the instrument's *IDN
print('connected to: ' + resp) # Print *IDN


# initializations .. 

inst.send_scpi_cmd('*CLS; *RST')
print('awg reset') 

#AWG channel 1
print('Setting up CH 1...') 
inst.send_scpi_cmd(':INST:CHAN 1')
print('CH I DAC Clk Freq {0}'.format(sampleRateDAC))
cmd = ':FREQ:RAST {0}'.format(sampleRateDAC)
inst.send_scpi_cmd(cmd)
inst.send_scpi_cmd(':INIT:CONT ON')
inst.send_scpi_cmd(':TRAC:DEL:ALL')

# Setup the digitizer 
print('Setting up Digitizer..') 
inst.send_scpi_cmd('DIG:ACQ:ZERO:ALL 0')
inst.send_scpi_cmd(':DIG:MODE SING') #set digitizer mode (single or double)
print('ADC Clk Freq {0}'.format(sampleRateADC))
cmd = ':DIG:FREQ  {0}'.format(sampleRateADC)
inst.send_scpi_cmd(cmd)

# Enable capturing data from channel 1
inst.send_scpi_cmd(':DIG:CHAN:SEL 1') #Select channel 1
inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB') #Enable channel 1
# Select the internal-trigger as start-capturing trigger:


# Select the frames for the capturing 
# (all the four frames in this example)

    
def makePulseData(cycles = 10):
    global dacWaveI
    global dacWaveQ
    
    ampI = 0.75  
    ampQ = 0.75 
    max_dac=65535
    half_dac=max_dac/2
    data_type = np.uint16
    
    #Set waveform length
    segLen = 1024 # Signal
    segLenDC = 1024 #DC
    

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
    

def downLoad_waveform_lowFreq(ch=1, segnum = 1):
    global dacWaveI
    global dacWaveQ
     
    dacWaveIQ = dacWaveI
    
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
    print('writing waveform to CH {0}'.format(ch))
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    

    cmd = ':OUTP ON'
    inst.send_scpi_cmd(cmd)
   

def setTaskDUC():
   
    ch=1
    #Direct RF Output CH
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    cmd = ':TASK:COMP:LENG 2'
    inst.send_scpi_cmd(cmd)
     
    cmd = ':TASK:COMP:SEL 1' 
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:SEGM 1'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:DTR ON'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:NEXT1 2'
    inst.send_scpi_cmd(cmd)
    '''
    cmd = ':TASK:COMP:SEL 2' 
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:SEGM 2'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:DTR ON'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:NEXT1 1'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:WRITE'
    inst.send_scpi_cmd(cmd)
    '''    
    cmd = ':SOUR:FUNC:MODE TASK'
    inst.send_scpi_cmd(cmd)         
    
    inst.send_scpi_cmd(':DIG:TRIG:SOURCE TASK1')

    
def acquireData():
    
    #Set number of frames to be collected
    numframes, framelen = 10, 3648
    totlen = numframes * framelen
    
    cmd = ':DIG:ACQuire:FRAM:DEF {0},{1}'.format(numframes, framelen)
    inst.send_scpi_cmd(cmd)
    
    capture_first, capture_count = 1, numframes

    # Start the digitizer's capturing machine
    inst.send_scpi_cmd(':DIG:INIT ON')
    cmd = ':DIG:ACQuire:FRAM:CAPT {0},{1}'.format(capture_first, capture_count)
    inst.send_scpi_cmd(cmd)
    
    ### Stop the digitizer capture
    inst.send_scpi_cmd(':DIG:INIT OFF')

    # Choose what to read 
    # (only the frame-data without the header in this example)
    inst.send_scpi_cmd(':DIG:DATA:TYPE FRAM')
    
    # Choose which frames to read (all in this example)
    
    
    #Ver 1: This works
    #inst.send_scpi_cmd(':DIG:DATA:SEL ALL')
    
    #Ver 2: This works (selecting a specific frame)
    inst.send_scpi_cmd(':DIG:DATA:SEL FRAM')
    inst.send_scpi_cmd(':DIG:DATA:FRAM 10,1')
    
    #Ver 3: This works (selecting arbitrary frames)
    #inst.send_scpi_cmd(':DIG:DATA:SEL FRAM')
    #inst.send_scpi_cmd(':DIG:DATA:FRAM 2,5')
    
    # Get the total data size (in bytes)
    resp = inst.send_scpi_query(':DIG:DATA:SIZE?')
    num_bytes = np.uint32(resp)
    print('Total read size in bytes: ' + resp)

    #### need to create matrix with correct dimensionality ### 
    wav1 = np.zeros((numframes, framelen), dtype=np.uint16)
    


    # Read the data that was captured by channel 1:
    rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)
    print(rc)
    
    wav1 = wav1-dcOff
    
    time.sleep(0.1)
    
    return wav1
    

makePulseData(cycles=20)
downLoad_waveform_lowFreq(ch=1, segnum=1)
setTaskDUC()

wav1 = acquireData()    
        
inst.close_instrument()
