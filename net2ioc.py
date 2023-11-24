#!/bin/python
import re
import argparse
import os.path

def CheckExt(choices):
    class Act(argparse.Action):
        def __call__(self,parser,namespace,fname,option_string=None):
            ext = os.path.splitext(fname)[1][1:]
            if ext not in choices:
                option_string = '({})'.format(option_string) if option_string else ''
                parser.error("File doesn't end with one of: {}".format(', '.join(choices)))
            else:
                setattr(namespace,self.dest,fname)
    return Act

def paeseNetlist(netlist_file, comp):
    netname=""
    nodename=""

    r_net = r"\(net \(code \"\d{1,}\"\) \(name \"([^\"]{1,})\"\)"
    r_node = "\(node \(ref \"" + comp + "\"\) \(pin \"\d{1,}\"\) \(pinfunction \"([^\"]{1,})\"\)" #.format as not appliable
    r_port = r"P[A,B,C,D]"

    port_dict = {}

    for line in netlist_file:
        if (m := re.search(r_net, line)):
            netname = m.group(1)

        if (m := re.search(r_node, line)):
            nodename = m.group(1)
        else:
            nodename = ""

        if (len(netname)>0 and len(nodename)>0 and re.match(r_port, nodename)):
            port_dict[nodename] = netname.replace('/', "")
    return port_dict

def patch_ioc(netlist, comp, ioc):
    with open(netlist, 'r') as file:
        pinnames = paeseNetlist(file, comp)
        file.close()

    with open(ioc, 'r') as file:
        iocdata = file.read()
        file.close()

    r_pinsNb = "Mcu.PinsNb=(\d{1,})"
    if (m := re.search(r_pinsNb, iocdata)):
        pins_nb = int(m.group(1))

    # Patch ioc :C
    for pin, name in pinnames.items():
        r_pinMcuDef = "Mcu.Pin\d{1,}="+pin
        r_pinLabel = pin+".GPIO_Label=.{1,}"
        r_pinParameters = pin+".GPIOParameters=.{1,}"
        r_pinParameters_label = pin+".GPIOParameters=.{0,}GPIO_Label"
        newLabel = "{}.GPIO_Label={}".format(pin, name)

        # Step 1: If no Mcu.Pin\d=pin, then add Mcu.Pin\d, Locked=true, Signal=GPIO_Input, increment pins_nb
        if (not re.search(r_pinMcuDef, iocdata)):
            print("Warning: Pin {} not present in ioc file! Configuring as input".format(pin))
            iocdata += "Mcu.Pin{}={}\n".format(pins_nb, pin)
            iocdata += "{}.Signal=GPIO_Input\n".format(pin)
            iocdata += "{}.Locked=true\n".format(pin)
            pins_nb += 1

        # Step 2: If no pin.GPIOParameters=, then add pin.GPIOParameters=GPIO_Label, else add GPIO_Label parameter
        if (m := re.search(r_pinParameters, iocdata)):
            if (not re.search(r_pinParameters_label, iocdata)):
                iocdata = re.sub(r_pinParameters, m.group(0)+",GPIO_Label", iocdata)
        else:
            iocdata += "{}.GPIOParameters=GPIO_Label\n".format(pin)

        # Step 3: If no pin.GPIO_Label=, then add, else patch
        if (re.search(r_pinLabel, iocdata)):
            iocdata = re.sub(r_pinLabel, newLabel, iocdata)
        else:
            iocdata += newLabel + "\n"

    iocdata = re.sub(r_pinsNb, "Mcu.PinsNb={}".format(pins_nb), iocdata)

    with open(ioc, 'w') as file:
        file.write(iocdata)
        file.close()

parser = argparse.ArgumentParser(description='KiCad STM32 MCU netlist to STM32CubeMX converter. Make an .ioc backup befor use!')
parser.add_argument('netlist', type=str, help='KiCad netlist (*.net)', action=CheckExt({"net"}))
parser.add_argument('comp', type=str, help='STM32 component name, ex. U1')
parser.add_argument('ioc', type=str, help='STM32CubeMX project file (*.ioc)', action=CheckExt({"ioc"}))
args = parser.parse_args()

patch_ioc(args.netlist, args.comp, args.ioc)
