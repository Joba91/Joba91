"""Gimbal project targets whose service protocol is still unverified."""
from vision_targets import target_info

FLIP = 'DJI Flip'
GIMBAL_PROJECTS = {FLIP: {'firmware_declared':'01.00.1500',
    'firmware_source':'declarado por el usuario', 'requested_calibrations':['JointCoarse','LinearHall'],
    'calibration_available':False,'factory_commands_verified':False,'internal_product_code':None}}


def usb_target_info(model):
    if model in GIMBAL_PROJECTS: return dict(GIMBAL_PROJECTS[model])
    return target_info(model)
