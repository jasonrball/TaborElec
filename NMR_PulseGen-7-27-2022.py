import os
import sys
srcpath = os.path.realpath('../SourceFiles')
sys.path.append(srcpath)
from teproteus import TEProteusAdmin as TepAdmin
from teproteus import TEProteusInst as TepInst

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

sid = 4
Debug = False

# Connect 
admin = TepAdmin()
inst = admin.open_instrument(slot_id=sid)# Get the instrument's *IDN
resp = inst.send_scpi_query('*IDN?')
print(resp)

#Set waveform param

#DC 
dcOffTime = 40e-6
dcPulses = 1

#Pi Pulse
piOnTime = 15e-6
piOffTime = 85e-6
piPulses = 1

#Pi 2 Pulse
pi2OnTime = 30e-6
pi2OffTime = 70e-6
pi2Pulses = 5

#Set NCO
carrierFreq = 75E6

#Set DAC
ch = 1
#sampleRateDAC = 2.2E9
sampleRateDAC = 1E9
interp = 4
gran = 32

#Set ADC
sampleRateADC = (sampleRateDAC * 32) / 20 # This ratio is required for clock sync
#sampleRateADC = 1.6E9 
digDelay = 0 #400E-9
digGran = 96
framelen = (sampleRateADC * pi2OnTime) 
framelen = int(digGran * round(framelen / digGran))
numframes = piPulses + pi2Pulses

#Reserve Ememory for Frames to Aquired.
totlen = numframes * framelen
wav1 = np.zeros(totlen, dtype=np.uint16)

#set up plot Axis
fftPlot = np.zeros(int(framelen/2), dtype=np.uint16)
xT = range(numframes * framelen)
xF = range(int(framelen/2))
dcOff = 50

dacWaveI = []
dacWaveQ = []

# initializations .. 

inst.send_scpi_cmd('*CLS; *RST')
inst.send_scpi_cmd(':INST:CHAN ' + str(ch))

print('CH {0} DAC Clk Freq {1}'.format(ch, sampleRateDAC))
cmd = ':FREQ:RAST {0}'.format(sampleRateDAC)
inst.send_scpi_cmd(cmd)
inst.send_scpi_cmd(':INIT:CONT OFF')
inst.send_scpi_cmd(':TRAC:DEL:ALL')
    
def makePulseData(onTime, offTime):
    global dacWaveI
    global dacWaveQ
    
    ampI = 1  
    ampQ = 1  
    max_dac=65535
    half_dac=max_dac/2
    data_type = np.uint16
    
    if(onTime > 0 ):
        segLen = (sampleRateDAC * onTime) /2
        segLen = int(gran * round(segLen / gran))  
        
        dacWaveI = np.ones(segLen) + max_dac

        dacWaveI = dacWaveI.astype(data_type)
    
    #Set DC
    segLenDC = (sampleRateDAC * offTime) /2
    segLenDC = int(gran * round(segLenDC / gran)) 
    
    dacWaveDC = np.zeros(segLenDC)       
    dacWaveDC = dacWaveDC + half_dac
    dacWaveDC = dacWaveDC.astype(np.uint16)
    
    if(onTime > 0 ):
        dacWaveI = np.concatenate([dacWaveI, dacWaveDC])
    else:
        dacWaveI = dacWaveDC
        
    #plt.plot(dacWaveI)
    #plt.show()
        
    dacWaveQ = dacWaveI 
    
    dacWaveQ = dacWaveQ.astype(data_type)


def downLoad_IQ_DUC(ch, segNum):
    global dacWaveI
    global dacWaveQ
    
    arr_tuple = (dacWaveI, dacWaveQ)
    dacWaveIQ = np.vstack(arr_tuple).reshape((-1,), order='F')  

    # Select channel
    cmd = ':INST:CHAN {0}'.format(ch)
    inst.send_scpi_cmd(cmd)

    # Define segment
    cmd = ':TRAC:DEF {0}, {1}'.format(segNum, len(dacWaveIQ))
    inst.send_scpi_cmd(cmd)

    # Select the segment
    cmd = ':TRAC:SEL {0}'.format(segNum)
    inst.send_scpi_cmd(cmd)

    # Increase the timeout before writing binary-data:
    inst.timeout = 30000
    # Send the binary-data with *OPC? added to the beginning of its prefix.
    inst.write_binary_data('*OPC?; :TRAC:DATA', dacWaveIQ)
    # Set normal timeout
    inst.timeout = 10000

    resp = inst.send_scpi_query(':SYST:ERR?')
    print("Download Complete, code " + resp)
    
def setFreq():
    
    cmd = ':SOUR:INT x' + str(interp)
    print("Interpolation: " + cmd)
    #cmd = ':SOUR:INT x8'
    rc = inst.send_scpi_cmd(cmd)

    sampleRateDACInt = sampleRateDAC * interp
    cmd = ':FREQ:RAST {0}'.format(sampleRateDACInt)
    rc = inst.send_scpi_cmd(cmd) 

    cmd = ':SOUR:MODE DUC'
    rc = inst.send_scpi_cmd(cmd)

    cmd = ':SOUR:IQM ONE'
    rc = inst.send_scpi_cmd(cmd)

    cmd = ':SOUR:NCO:CFR1 {0}'.format(carrierFreq)
    rc = inst.send_scpi_cmd(cmd)

    # cmd = ':SOUR:SIXD ON'
    # rc = inst.send_scpi_cmd(cmd)

    print('Sample Clk Freq {0}'.format(sampleRateDACInt))
    cmd = ':FREQ:RAST {0}'.format(sampleRateDACInt)
    rc = inst.send_scpi_cmd(cmd)
    
    resp = inst.send_scpi_query(':SYST:ERR?')
    print("CW Set, code " + resp)

    cmd = ':OUTP ON'
    inst.send_scpi_cmd(cmd)

def setTaskDUC():
   
    tak_half_dac = 0x80
    
    #Direct RF Output CH 1
    inst.send_scpi_cmd(':INST:CHAN ' + str(ch))
    
    taskEntry = 1

    #Define Task Length
    cmd = ':TASK:COMP:LENG ' + str(dcPulses + piPulses + pi2Pulses)  # +1 is the exit task
    print(cmd)
    inst.send_scpi_cmd(cmd)
    
    #Define Tasks
    cmd = ':TASK:COMP:SEL ' + str(taskEntry)
    print(cmd)
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:ENAB INT'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:LOOP 1' 
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:SEGM 1' #DC
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:DTR ON'
    inst.send_scpi_cmd(cmd)
    cmd = ':TASK:COMP:NEXT1 2'
    inst.send_scpi_cmd(cmd)
    
    taskEntry = taskEntry + 1
    
    for taskEntry in range(taskEntry, taskEntry+piPulses):
        cmd = ':TASK:COMP:SEL ' + str(taskEntry)
        print(cmd)
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:ENAB NONE'
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:TYPE START'
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:SEQ 1'
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:SEGM 2' #Pi
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:DTR ON'
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:NEXT1 ' + str(taskEntry+1)
        inst.send_scpi_cmd(cmd)
     
    if (piPulses !=0):
        taskEntry = taskEntry + 1
    
    for taskEntry in range(taskEntry, taskEntry+pi2Pulses):
        cmd = ':TASK:COMP:SEL ' + str(taskEntry)
        print(cmd)
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:SEGM 3' #pi2
        inst.send_scpi_cmd(cmd)
        cmd = ':TASK:COMP:DTR ON'
        inst.send_scpi_cmd(cmd)
        if(taskEntry == (dcPulses + piPulses + pi2Pulses)):
            cmd = ':TASK:COMP:NEXT1 0'
        else:
            cmd = ':TASK:COMP:NEXT1 ' + str(taskEntry+1)
        print(cmd)
        inst.send_scpi_cmd(cmd)
 
    cmd = ':TASK:COMP:WRITE'
    inst.send_scpi_cmd(cmd)
    
    # Put instrument in Task Mode
    cmd = ':SOUR:FUNC:MODE TASK'
    inst.send_scpi_cmd(cmd)
    
    resp = inst.send_scpi_query(':SYST:ERR?')
    print("Task set, code  " + resp) 
   
 
        
makePulseData(0, dcOffTime)
downLoad_IQ_DUC(ch, segNum=1)

makePulseData(piOnTime, piOffTime)
downLoad_IQ_DUC(ch, segNum=2)

makePulseData(pi2OnTime, pi2OffTime)
downLoad_IQ_DUC(ch, segNum=3)


setFreq() 

setTaskDUC()


# Setup the digitizer (two-channels opperation)
inst.send_scpi_cmd(':DIG:MODE SING')
inst.send_scpi_cmd(':DIG:FREQ ' + str(sampleRateADC))

resp = inst.send_scpi_query(":DIG:FREQ?")
print("Digitizer Sample Clk: " + resp)

#inst.send_scpi_cmd(':DIG:DDC:CLKS AWG') # Sync DAC and ADC clock with sample ratio

cmd = ':DIG:ACQuire:FRAM:DEF {0},{1}'.format(numframes, framelen)
inst.send_scpi_cmd(cmd)

# Select the frames to capture
capture_first = 1
cmd = ":DIG:ACQuire:FRAM:CAPT {0},{1}".format(capture_first, numframes)
inst.send_scpi_cmd(cmd)


# Enable capturing data from channel 1
inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB')
# Select the internal-trigger as start-capturing trigger:
inst.send_scpi_cmd(':DIG:TRIG:SOURCE TASK1')


inst.send_scpi_cmd(':DIG:TRIG:AWG:TDEL {}'.format(digDelay) )
resp = inst.send_scpi_query(':DIG:TRIG:AWG:TDEL?')
print("Digitizer Trigger Delay: "+resp)

# Clear memory 
inst.send_scpi_cmd(':DIG:ACQ:ZERO:ALL')

print("Digitizer setup complete!")

# Start the capture
print("Starting Capture.....")
# Halt digitizer's capturing machine 
inst.send_scpi_cmd(':DIG:INIT OFF')

# Start the digitizer's capturing machine
inst.send_scpi_cmd(':DIG:INIT ON')

inst.send_scpi_cmd(':TRIGger:COUPle 1') # Maybe not required.
inst.send_scpi_cmd('*TRG')

for _ in range(numframes*2):
    #inst.send_scpi_query(':DIG:TRIG:IMM')
    time.sleep(0.1) # more than  enough for capturing single frame
    # Query the status
    resp = inst.send_scpi_query(":DIG:ACQuire:FRAM:STATus?")
    print(resp)
    
print("Capture Done")
    

# Choose which frames to read (all in this example)
inst.send_scpi_cmd(':DIG:DATA:SEL ALL')

# Choose what to read 
# (only the frame-data without the header in this example)
inst.send_scpi_cmd(':DIG:DATA:TYPE FRAM')

# Get the total data size (in bytes)
resp = inst.send_scpi_query(':DIG:DATA:SIZE?')
num_bytes = np.uint32(resp)
print('Total size in bytes: ' + resp)
print()

# Read the data that was captured by channel 1:
inst.send_scpi_cmd(':DIG:CHAN:SEL 1')

wavlen = num_bytes // 2

wav1 = np.zeros(wavlen, dtype=np.uint16)

rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)

# Stop the digitizer's capturing machine (to be on the safe side)
inst.send_scpi_cmd(':DIG:INIT OFF')

resp = inst.send_scpi_query(':SYST:ERR?')
print("Complete, code " + resp)

print("Digitizer: Finish Acquisition")

plt.plot(wav1)
plt.show()
