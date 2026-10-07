import numpy as np

def validity_check(header, data):
    """ Basic checks if the header and data are consistent. """
    # Check if the header and data are consistent.
    if header['VERSION'][0] not in ['0.7', '0.7.0', '.7']:
        raise ValueError('Only .pcd version 0.7 is supported.')
    if header['POINTS'][0] != str(data.size(0)):
        raise ValueError('Number of points in header and data do not match.')
    if len(header['FIELDS']) != len(header['TYPE']) != len(header['COUNT']) != data.size(1):
        raise ValueError('Number of fields in header and data do not match.')
    if header['HEIGHT'][0] != '1':
        raise ValueError('Only organized PCDs are supported.')

def read_pcd_array(path, start=0, end=None, dtype=None, device=None):
    """ Loads a point cloud from a .pcd file. See https://pointclouds.org/documentation/tutorials/pcd_file_format.html for more details. """
    with open(path, 'r') as f:
        src = f.read().split('\n')[:-1]
        # Remove all strings starting with '#'.
        src = [line for line in src if not line.startswith('#')]
        # Header is first 10 lines of the file.
        header = src[0:10]
        # Parse the header. Format is: 'key value'.
        header = {line.split(' ')[0]: line.split(' ')[1:] for line in header}
        if header['DATA'][0] != 'ascii':
            raise ValueError('Only ASCII .pcd files are supported.')

        # Data starts at line 11.
        data = np.array([line.split(' ') for line in src[10:]], dtype=float)
        validity_check(header, data)

    return data


