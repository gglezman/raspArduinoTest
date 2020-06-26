#
# Author: Greg Glezman
#
# SCCSID : "%W% %G%
#
# Copyright (c) 2019 G.Glezman.  All Rights Reserved.
#

from time import sleep
from smbus2 import SMBus
# import threading


class I2C_Transport:
    def __init__(self, bus):
        self.smbus = SMBus(bus=bus)
        sleep(1)   # give the bus a chance to settle
        # print("Bus settled")

    def loopback_test(self, adr):
        """Execute a loopback test on the given address

        A loopback test consists of the following message sent 256 times
        to the given adr:
             block data read to
             - register 99

        The  return value is a tuple (messagesSent, readExceptions).
        """
        messages_to_send = 256
        read_exception = 0
        for i in range(messages_to_send):
            try:
                self.smbus.read_i2c_block_data(adr, 99, 2)  # 2=length
            except IOError:
                read_exception += 1
                print("Read IOerror at adr {} on msg {}".format(adr,i))
            sleep(0.00001)

        return messages_to_send, read_exception
                      
    def Xloopback_test_write(self, adr):
        """Execute a loopback test on the given address

        A loopback test consists of the following message sent 256 times
        to the given adr:
             block data write to
             - register 100
             - data [d1, d2, d3]
             block data read from 
             - register 100, 1+3 bytes (regId and data)

        The  return value is a tuple (messagesSent, resendCount).
        """
        messages_to_send = 256
        write_exception = 0
        read_exception = 0
        multi_read_faiulre = 0
        
        length = 4   # '100' plus 3 bytes of data
        
        for i in range(messages_to_send):
            d1 = i % 256
            d2 = (i+1 )%256
            d3 = (i+2) % 256
            cs = (d1+d2+d3) % 256 
            for retry in range(1,5):
                try:
                    # do the write
                    #print("Write attempt {} for {} ".format(retry,i))
                    self.smbus.write_i2c_block_data(adr, 100, [d1, d2, d3, cs])
                    break
                except IOError:
                    write_exception += 1
                    print("Write exception {} at adr {}".format(
                        write_exception, adr))

            sleep (0.0001)
            
            for attempt in range(1,5):
                try:
                    # do the read/verify
                    read_data = self.smbus.read_i2c_block_data(adr, 100, length)
                    if len(read_data) != length:
                        print("Read verify length mismatch {}/{}".format(
                            len,len(read_data)))
                    if read_data[0] == 100 and \
                       read_data[1] == d1 and \
                       read_data[2] == d2 and \
                       read_data[3] == d3:
                        break
                    '''
                    else:
                        print("data mismatch({}) {}, {}, {}, {}".format(
                            attempt, 100, d1,d2,d3))
                        print("data is {}, {}, {}, {}".format(
                            read_data[0], read_data[1],
                            read_data[2], read_data[3]))
                        # break;
                    '''
                except IOError:
                    read_exception += 1
                    print("Read exception {} at adr {}".format(
                        read_exception, adr))

            if attempt >= 4:
                multi_read_failure += 1
                print("Multi-Read Faulre")
            sleep(0.0001)

        return messages_to_send, write_exception+read_exception

    def loopback_test_write(self, adr):
        """Execute a loopback test on the given address

        A loopback test consists of the following message sent 256 times
        to the given adr:
             block data write to
             - register 100
             - data [d1, d2, d3]
             block data read from 
             - register 100, 1+3 bytes (regId and data)

        The  return value is a tuple (messagesSent, resendCount).
        """
        
        messages_to_send = 256
        reg = 100                 # loopback register

        write_exception = 0
        read_exception = 0
        data_mismatch = 0
        uncorrectable_err = 0
        
        for i in range(messages_to_send):
            d1 = i % 256
            d2 = (i+1 )%256
            d3 = (i+2) % 256
            cs = (d1+d2+d3) % 256 

            for attempt in range (1,5):
                pf, we = self.write_func(adr, reg, [d1, d2, d3, cs])
                write_exception += we
                if pf == 0:
                    #sleep(.001)
                    pf, re, dm = self.read_verify(adr, reg, [d1, d2, d3])
                    read_exception += re
                    data_mismatch += dm
                    if pf == 0:
                        break
            if attempt >= 4:
                uncorrectable_err += 1
        errors =  write_exception+read_exception+data_mismatch+uncorrectable_err
        if errors > 0:
            print("we {}, re {}, dm {}, unerr {}".format(write_exception,
                                                         read_exception,
                                                         data_mismatch,
                                                         uncorrectable_err))
        return messages_to_send, read_exception, write_exception,\
               data_mismatch, uncorrectable_err

    def write_func(self, adr, reg, data):
        '''Write given data to the given address.
        Inputs
           adr - I2C bus adr
           reg - register at ard to write to
           data - list of bytes to write

        Make n attempts to write the  data to adr/register.
        If an IOError occurs during the write, count it and retry.

        return 
            result  0 : success, data was written, may have taken retries
                   -1 : failure, unable to write data
            write_exception - number of IOErrors encountered
        '''
        write_exception = 0
        result = -1     # assume failure
        
        for attempt in range(1,5):
            try:
                # do the write
                self.smbus.write_i2c_block_data(adr, reg, data)
                result = 0
                break
            except IOError:
                write_exception += 1
                #print("Write excep {} at adr {}".format(write_exception,adr))
                sleep(0.001)
            
        return result, write_exception

    def read_verify(self, adr, reg, data):
        '''Read from the given address and verify the data
        Inputs
           adr - I2C bus adr
           reg - register at ard to write to
           data - list of bytes to verify

        Make n attempts to read from the given adr/register and verify the data.
        If an IOError occurs during the read, count it and retry.
        If the data does not match, count it and retry.

        return 
            result  0 : success, data was verified, may have taken retries
                   -1 : failure, unable to verify data
            read_exception - number of IOErrors encountered
            data_mismatch - number of data mismatches encountered
        '''
        read_exception = 0
        data_mismatch = 0
        result = -1            # assume failure
        length = len(data) + 1 # 1 is for regId also returned by read      
        
        for attempt in range(1,5):
            try:
                # do the read/verify
                read_data = self.smbus.read_i2c_block_data(adr, reg, length)
                error = 0
                data.insert(0,reg)          # Put the reg in the data list
                for i in range(0,length):   # 0 through length-1
                    if read_data[i] != data[i]:
                        data_mismatch += 1
                        error = 1
                        break
                if error == 0:
                   result = 0
                   break

            except IOError:
                read_exception += 1
                #print("Read exception {} at adr {}".format(read_exception,adr))
                sleep(0.0001)
    
        return result, read_exception, data_mismatch

        
