#
# Author: Greg Glezman
#
# SCCSID : "%W% %G%
#
# Copyright (c) 2019-2020 G.Glezman.  All Rights Reserved.
#

from time import sleep
from smbus2 import SMBus
# import threading


class I2C_Transport:
    def __init__(self, bus):
        self.smbus = SMBus(bus=bus)
        self.write_seq_num = 0

        sleep(1)   # give the bus a chance to settle
        # print("Bus settled")


    def block_read_test(self, adr, reg):
        """Execute a block read test on the given address / register

        A loopback test consists of the following message sent 256 times
        to the given adr:
             block data read to
             - register 'reg'

        The  return value is a tuple (messagesSent, readExceptions, data_mismatches).
        """
        messages_to_send = 256
        read_exception = 0
        data_mismatch = 0
        for i in range(messages_to_send):
            try:
                read_data = self.smbus.read_i2c_block_data(adr, reg, 3)  # regId, data, checksum
                if read_data[0] != reg or read_data[1] != read_data[2]:
                    data_mismatch += 1
                    if read_data[0] != reg:
                        print("RegId read error")
                    if read_data[1] != read_data[2]:
                        print("Checksum error: {} {} ".format(read_data[1], read_data[2]))
            except IOError:
                read_exception += 1
                print("Read IOerror at adr {} on attempt # {}".format(adr,i))
            sleep(0.00001)

        return messages_to_send, read_exception, data_mismatch
                      

    def loopback_test_write(self, adr, reg):
        """Execute a loopback test on the given address

        A loopback test consists of the following message sent 256 times
        to the given adr:
             block data write to
             - register 100
             - data [d1, d2, d3, cs]
             block data read from 
             - register 100, 1+3+1 bytes (regId and data and cs)

        The  return value is a tuple (
                 messages_sent,
                 read_exception,
                 write_exception,
                 data_mismatch,
                 uncorrectable_errors
        """
        messages_to_send = 256

        write_exception = 0
        read_exception = 0
        data_mismatch = 0
        uncorrectable_err = 0

        for i in range(messages_to_send):
            # generate the data
            data = [ i % 256, (i+1) % 256, (i+2) % 256 ]

            # do the write
            ue, re, we, dm = self.write_verify(adr, reg, data)

            # update the results
            uncorrectable_err += ue
            read_exception += re
            write_exception += we
            data_mismatch += dm

        return messages_to_send, read_exception, write_exception,\
               data_mismatch, uncorrectable_err

    def write_verify(self, adr, reg, data):
        """Do a single write / verify test with retries on the write and read back"""
        write_exception = 0
        read_exception = 0
        data_mismatch = 0
        final_result = 0

        for attempt in range(1, 5):
            result, we = self.write_func(adr, reg, data)
            write_exception += we
            if result == 0:
                # todo - .5 slows things down enough to print in the main Arduino loop if necessary
                #   I also used .1 to process buffers in the main loop prior to changing verify
                #   from reading data back to reading sequence number back.
                #sleep(.001)
                result, re, dm = self.read_verify(adr, 19, [self.write_seq_num])
                read_exception += re
                data_mismatch += dm
                if result == 0:
                    break
        if attempt >= 4:
            final_result = 1
        errors = write_exception + read_exception + data_mismatch + final_result
        if errors > 0:
            print("we {}, re {}, dm {}, unerr {}".format(write_exception,
                                                         read_exception,
                                                         data_mismatch,
                                                         final_result))
        return final_result, read_exception, write_exception, data_mismatch

    def write_func(self, adr, reg, data):
        '''Write given data to the given address / register
        Inputs
           adr - I2C bus adr
           reg - register to write to
           data - list of bytes to write
        Generate a simple checksum and append it to the data
        Make n attempts to write the data to adr/register.
        If an IOError occurs during the write, count it and retry.

        return 
            result  0 : success, data was written, may have taken retries
                   -1 : failure, unable to write data
            write_exception - number of IOErrors encountered
        '''
        write_exception = 0
        result = -1     # assume failure

        # generate a checksum
        cs = 0
        for i in data:
            cs += i

        cs %= 256

        for attempt in range(1,5):
            try:
                self.write_seq_num = (self.write_seq_num+1) % 256
                cs = reg + self.write_seq_num
                for d in data:
                    cs += d
                cs = - (cs % 256)
                #print("cs {}".format(cs))
                #print("try seq_num {}".format(self.write_seq_num))
                self.smbus.write_i2c_block_data(adr, reg, [self.write_seq_num] + data + [cs] )
                result = 0
                break
            except IOError:
                # delete me
                #print("Write exception {}".format(self.write_seq_num))
                #sleep(.01)
                write_exception += 1
            
        return result, write_exception

    def read_verify(self, adr, reg, data):
        """Read from the given address/register and verify the expected_data
        Inputs
           adr - I2C bus adr
           reg - register to read from
           data - list of bytes expected

        Make n attempts to read from the given adr/register and verify the expected_data.
        If an IOError occurs during the read, count it and retry.
        If the expected_data does not match, count it and retry.

        return 
            result  0 : success, data was verified, may have taken retries
                   -1 : failure, unable to verify data
            read_exception - number of IOErrors encountered
            data_mismatch - number of data mismatches encountered
        """
        read_exception = 0
        data_mismatch = 0
        result = -1                      # assume failure
        # generate a checksum
        cs = 0
        for i in data:
            cs += i
        cs %= 256
        expected_data = [reg] + data + [cs]  # Put the reg in the data list. Its part of the return data
        length = len(expected_data)

        # take me out -
        #print("Expected {}".format(expected_data))

        for attempt in range(1,5):    # 4 retries for now
            try:
                # do the read/verify
                read_data = self.smbus.read_i2c_block_data(adr, reg, length)
                error = 0
                for i in range(0,length):   # 0 through length-1
                    if read_data[i] != expected_data[i]:
                        # delete me
                        #print("read {}  expected  {}".format(read_data, expected_data))
                        data_mismatch += 1
                        error = 1
                        break
                if error == 0:
                   result = 0
                   break

            except IOError:
                read_exception += 1

        return result, read_exception, data_mismatch

        
