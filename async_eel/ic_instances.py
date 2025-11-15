from icecream import IceCreamDebugger

# Registry
IC_INSTANCES = []

def create_ic(prefix=""):
    ic = IceCreamDebugger(prefix=prefix)
    IC_INSTANCES.append(ic)
    return ic

# Disable globally:
def disable_all():
    for instance in IC_INSTANCES:
        instance.disable()

def enable_all():
    for instance in IC_INSTANCES:
        instance.enable()
