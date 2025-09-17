"""

    Ported utility for MeshID handling from: https://gist.github.com/developerfromjokela/0acf80b6292c22f7a2aa7a3227883e82

"""

import ctypes


class UnpackedMeshID(ctypes.Structure):
    _fields_ = [
        ("val1", ctypes.c_uint),
        ("val2", ctypes.c_uint),
        ("val3", ctypes.c_uint),
        ("val4", ctypes.c_uint),
        ("val5", ctypes.c_uint),
        ("val6", ctypes.c_uint),
    ]


class MapPoint(ctypes.Structure):
    _fields_ = [
        ("lat", ctypes.c_int32),
        ("lon", ctypes.c_int32),
    ]


class MeshPoint(ctypes.Structure):
    _fields_ = [
        ("meshID", ctypes.c_uint32),
        ("x", ctypes.c_int16),
        ("y", ctypes.c_int16),
    ]


def unpack_mesh_id(mesh_id: ctypes.c_uint32, unpacked_mesh_id: UnpackedMeshID) -> None:
    if not unpacked_mesh_id:
        return

    uVar1: ctypes.c_uint = ctypes.c_uint((mesh_id.value >> 0x17) & 0x7f)
    unpacked_mesh_id.val1 = uVar1
    unpacked_mesh_id.val3 = ctypes.c_uint((mesh_id.value >> 0x14) & 7)
    unpacked_mesh_id.val5 = ctypes.c_uint((mesh_id.value >> 0x10) & 0xf)
    uVar2: ctypes.c_uint= ctypes.c_uint((mesh_id.value >> 7) & 0x1ff)
    unpacked_mesh_id.val4 = ctypes.c_uint((mesh_id.value >> 4) & 7)
    unpacked_mesh_id.val6 = ctypes.c_uint(mesh_id.value & 0xf)
    unpacked_mesh_id.val2 = uVar2

    if mesh_id.value & 0x40000000:
        unpacked_mesh_id.val1 = ctypes.c_uint(uVar1.value | 0xffffff80)
    if mesh_id.value & 0x80000000:
        unpacked_mesh_id.val2 = ctypes.c_uint(uVar2.value | 0xfffffe00)


def mesh_id_judge_level(mesh_id: ctypes.c_uint32) -> int:
    decoded_headerinfo = ((mesh_id.value >> 0xc & 0xff) ^ (mesh_id.value & 0xff)) & 0xf ^ (mesh_id.value >> 0xc & 0xff)

    if decoded_headerinfo == 0xf2:
        return 2
    elif decoded_headerinfo == 0xf3:
        return 3
    elif decoded_headerinfo == 0xf4:
        return 4
    elif decoded_headerinfo == 0xf5:
        return 5
    elif decoded_headerinfo == 0xf6:
        return 6
    else:
        level = 1
        if mesh_id.value & 0xc000c:
            level = 0x7fff
        return level


def validate_mesh_id(mesh_id: ctypes.c_uint32, level: ctypes.POINTER(ctypes.c_int16)) -> bool:
    if not level or mesh_id == 0:
        return False
    judgeLvl = mesh_id_judge_level(mesh_id)
    level[0] = judgeLvl

    if judgeLvl == 0x7fff:
        return False

    unpackedMeshId = UnpackedMeshID()
    unpack_mesh_id(mesh_id, unpackedMeshId)

    if judgeLvl == 1:
        return (unpackedMeshId.val3 < 8 and
                unpackedMeshId.val4 < 8 and
                unpackedMeshId.val5 < 4 and
                unpackedMeshId.val6 < 4)
    elif judgeLvl == 2:
        return unpackedMeshId.val3 < 8 and unpackedMeshId.val4 < 8
    elif judgeLvl == 3:
        if unpackedMeshId.val3 not in (0, 1):
            return False
        return unpackedMeshId.val4 in (0, 1)
    elif judgeLvl == 4:
        uVar2 = unpackedMeshId.val1 & 1
        if unpackedMeshId.val1 < 0 and uVar2 != 0:
            uVar2 = uVar2 - 2
        if uVar2 != 0:
            return False
        uVar2 = unpackedMeshId.val2 & 1
        if unpackedMeshId.val2 < 0 and uVar2 != 0:
            uVar2 = uVar2 - 2
        return uVar2 == 0
    elif judgeLvl == 5:
        uVar2 = unpackedMeshId.val1 & 7
        if unpackedMeshId.val1 < 0 and uVar2 != 0:
            uVar2 = uVar2 - 8
        uVar1 = -(uVar2 & 0x80000000)
        if (uVar2 ^ uVar1) != uVar1:
            return False
        uVar2 = unpackedMeshId.val2 & 7
        if unpackedMeshId.val2 < 0 and uVar2 != 0:
            uVar2 = uVar2 - 8
        uVar1 = -(uVar2 & 0x80000000)
        return (uVar2 ^ uVar1) == uVar1
    elif judgeLvl == 6:
        return mesh_id == 0x1fe200f6
    return True


def convert_to_utm(meshID: ctypes.c_int32, confchar: ctypes.c_int32) -> tuple[int, int, int]:
    mesh_scaling_table = [0.0, 32.0, 8.0, 2.0]
    out_lvl = (ctypes.c_int16 * 2)(0)

    mesh_id_return = validate_mesh_id(meshID, out_lvl)

    if mesh_id_return == 0:
        return 2, 0, 0

    unpacked_mesh_id = UnpackedMeshID()
    unpack_mesh_id(meshID, unpacked_mesh_id)

    mesh_id_return = out_lvl[0]
    d_var5 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val1).value).value)
    d_var4 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val2).value).value)

    if mesh_id_return == 1:
        dVar3 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val5).value).value) * 0.03125 + \
                float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val3).value).value) * 0.125
        dVar2 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val6).value).value) * 0.03125 + \
                float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val4).value).value) * 0.125
    elif mesh_id_return == 2:
        dVar3 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val3).value).value) * 0.125
        dVar2 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val4).value).value) * 0.125
    elif mesh_id_return == 3:
        dVar3 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val3).value).value) * 0.5
        dVar2 = float(ctypes.c_int64(ctypes.c_int32(unpacked_mesh_id.val4).value).value) * 0.5
    else:
        if mesh_id_return < 4 or mesh_id_return > 6:
            return 1, 0, 0

    d_var5 = dVar3 + d_var5
    d_var4 = dVar2 + d_var4

    if confchar == 1:
        dVar2 = 0.5 / mesh_scaling_table[mesh_id_return]
        if ctypes.c_int32(unpacked_mesh_id.val1).value < 0:
            d_var5 = d_var5 - dVar2
        else:
            d_var5 = dVar2 + d_var5
        if ctypes.c_int32(unpacked_mesh_id.val2).value < 0:
            d_var4 = d_var4 - dVar2
        else:
            d_var4 = dVar2 + d_var4

    lVar1 = 0
    return 0, int((d_var5 - float(lVar1)) * 0.6666666666666666 * 8388608.0), int(((d_var4 + 100.0) - float(lVar1)) * 8388608.0)

def mesh_point_is_valid(mesh_point: MeshPoint, level_out: ctypes.POINTER(ctypes.c_int16)) -> int:
    if not mesh_point:
        return 0

    mesh_id_valid = validate_mesh_id(ctypes.c_uint32(mesh_point.meshID), level_out)
    if (mesh_id_valid != 0 and
            mesh_point.y < 0x800 and
            mesh_point.y > -1 and
            mesh_point.x < 0x800 and
            mesh_point.x > -1):
        return 1
    return 0


def mesh_point_to_map_point(mesh_point: MeshPoint, map_point: MapPoint) -> bool:
    mesh_id_level = (ctypes.c_int16 * 2)(0)
    scaling_items = [128.0, 32.0, 8.0, 2.0]

    mesh_pnt_valid = mesh_point_is_valid(mesh_point, mesh_id_level)
    if mesh_pnt_valid == 0 or not map_point:
        return 2

    result, x, y = convert_to_utm(ctypes.c_uint32(mesh_point.meshID), 0)

    utm_lat = float(x) * 1.1920928955078125e-07
    utm_lon = float(y) * 1.1920928955078125e-07

    if mesh_point.x != 0 or mesh_point.y != 0:
        utm_lon = (float(mesh_point.x) * 0.00048828125) / scaling_items[mesh_id_level[0]] + utm_lon
        utm_lat = (float(mesh_point.y) * 0.00048828125) / scaling_items[mesh_id_level[0]] * 0.6666666666666666 + utm_lat

    map_point.lat = int(utm_lat * 3600.0 * 512.0)
    map_point.lon = int(utm_lon * 3600.0 * 512.0)
    return result == 0

def unpack_monster_id_to_mesh_id(monster: ctypes.c_uint32) -> ctypes.c_uint32:
    res = 0
    res |= (monster.value & 0xf)  # bits 0-3
    res |= ((monster.value >> 4 & 0xf) << 16)  # y 4-7 -> res 16-19
    res |= ((monster.value >> 8 & 0x7) << 4)  # y 8-10 -> res 4-6
    res |= ((monster.value >> 11 & 1) << 20)  # y11 -> res20
    res |= ((monster.value >> 12 & 1) << 21)  # y12 -> res21
    res |= ((monster.value >> 13 & 1) << 22)  # y13 -> res22
    res |= ((monster.value >> 14 & 1) << 7)  # y14 -> res7
    res |= ((monster.value >> 15 & 0xff) << 8)  # y15-22 -> res8-15
    res |= ((monster.value >> 23 & 1) << 31)  # y23 -> res31
    res |= ((monster.value >> 24 & 0xff) << 23)  # y24-31 -> res23-30
    return ctypes.c_uint32(res)

def read_big_endian_u_int32(buffer: bytes) -> ctypes.c_uint32:
    """Read a big-endian uint32 from a 4-byte buffer."""
    return ctypes.c_uint32((buffer[0] << 24) | (buffer[1] << 16) | (buffer[2] << 8) | buffer[3])