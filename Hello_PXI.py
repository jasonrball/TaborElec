# -*- coding: utf-8 -*-
"""
Created on Fri Jan  6 13:42:00 2023

@author: jason b. 

Checks if a module can be found via pxi 
"""

from teproteus import TEProteusAdmin as TepAdmin

# Connect to instrument(PXI)
sid = 4 #PXI slot of AWT on chassis
admin = TepAdmin() #required to control PXI module
inst = admin.open_instrument(slot_id=sid) 

resp = inst.send_scpi_query("*IDN?") # Get the instrument's *IDN
print('connected to: ' + resp) # Print *IDN
