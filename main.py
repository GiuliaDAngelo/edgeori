'''

%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%% READ ME %%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%

Author: Giulia D'Angelo
dangelo@fortiss.org

This code represents a prototype for edge orientation, it is a first attempt towards a neuromorphic implementation.
It uses

'''



import numpy as np
import matplotlib.pyplot as plt
# import snnTorch as snn  # Assuming you have snnTorch installed
from scipy.ndimage import convolve
from dv import AedatFile
import torchvision
import tonic
import torch
import numpy.lib.recfunctions as rf
import torch.nn as nn
from scipy.stats import multivariate_normal
import tensorflow as tf
from torchvision.utils import save_image



# Step 1: Data Collection
# Implement event data collection from the event-driven camera
def collect_event_data(path):
    with AedatFile(path) as f:
        load = np.hstack([packet for packet in f['events'].numpy()])
        x = load['x']
        y = load['y']
        p = load['polarity']
        t = load['timestamp']#time in microseconds
    min_ts=t.min()
    events = np.stack((x,y,p,t-min_ts), axis=-1)
    rec = rf.unstructured_to_structured(events,
                                        dtype=np.dtype(
                                            [('x', np.int16), ('y', np.int16), ('p', bool), ('t', int)]))
    return rec


# Step 2: Event Processing
# Preprocess the event data and convert it into a spatial-temporal representation
def preprocess_event_data(sensor_size, time_wnd_frames, events, animFLAG):
    transforms = torchvision.transforms.Compose([
        tonic.transforms.ToFrame(sensor_size=sensor_size, time_window=time_wnd_frames),
        torch.tensor,
    ])
    eventframes = transforms(events)
    if animFLAG:
        tonic.utils.plot_animation(frames=eventframes.numpy())
    return eventframes


# Step 3: Gaussian Multivariate Distribution Bank
# Define a bank of Gaussian distributions with different orientations
def multivariate_gaussian_kernel(size, sigma_x, sigma_y, angle):
    """
    Generate a 2D Gaussian multivariate kernel.

    Parameters:
    size (tuple): Size of the kernel in the form (height, width).
    sigma_x (float): Standard deviation along the x-axis.
    sigma_y (float): Standard deviation along the y-axis.
    angle (float): Rotation angle of the kernel in degrees.

    Returns:
    np.ndarray: 2D Gaussian multivariate kernel matrix.
    """
    # Create a covariance matrix
    cov = np.array([[sigma_x**2, 0], [0, sigma_y**2]])

    # Rotation matrix
    angle_rad = np.radians(angle)
    rotation_matrix = np.array([[np.cos(angle_rad), -np.sin(angle_rad)],
                                [np.sin(angle_rad), np.cos(angle_rad)]])

    # Generate meshgrid for coordinates
    x = np.arange(-(size[1]-1)/2, (size[1]+1)/2)
    y = np.arange(-(size[0]-1)/2, (size[0]+1)/2)
    X, Y = np.meshgrid(x, y)

    # Rotate and scale coordinates
    coords = np.stack([X, Y], axis=-1)
    coords = np.dot(coords, rotation_matrix.T)

    # Generate the kernel
    kernel = multivariate_normal.pdf(coords, mean=[0, 0], cov=cov)

    return kernel / np.sum(kernel)

def bank_MVG(size, sigma_x, sigma_y, angles, show_imgs, numangles):
    cn=0
    bankMVG = []
    for angle in angles:
        # bankMVG[cn,:,:] = torch.from_numpy(multivariate_gaussian_kernel(size, sigma_x, sigma_y, angle))
        kernel = torch.from_numpy(multivariate_gaussian_kernel(size, sigma_x, sigma_y, angle))
        bankMVG.append(kernel)
        # Plot the kernel matrix as a heatmap
        # plt.imshow(bankMVG[cn], cmap='hot', interpolation='nearest')
        # plt.title('Gaussian Multivariate Kernel')
        # plt.colorbar()
        # plt.show()
        cn+=1
    # show all the 9 orientations
    if show_imgs:
        rc= int(numangles/2)
        fig, axes = plt.subplots(2, rc, figsize=(10, 8))
        for i in range(0, len(angles)):
            if i < rc:
                ax=0
                ps=i
            else:
                ax = 1
                ps=i-rc
            axes[ax, ps].set_title(f"{angles[i]} grad")
            axes[ax, ps].imshow(bankMVG[i])
    return bankMVG


# Step 4: Convolution and Visualization
# Convolve the event map with each Gaussian distribution from the bank and visualize the results
def conv_vis(event_map, gaussian_kernel):
    convolved_map = convolve(event_map, gaussian_kernel)
    # # Visualize the result
    # plt.imshow(convolved_map, cmap='gray')  # Assuming grayscale visualization
    # plt.colorbar()
    # plt.show()
    return convolved_map

def soft_winner_take_all(angles, activations, threshold):
    winners = np.zeros_like(activations)
    for i in range(len(angles)):
        diff = np.abs(angles - angles[i])
        close_angles = np.where(diff < threshold)[0]
        total_activation = np.sum(activations[close_angles])
        winners[close_angles] += activations[close_angles] / total_activation
    return winners


if __name__ == "__main__":
    # Step 1: Data Collection
    # Collect event data from the event-driven camera for a specified time window
    path = 'microsaccades.aedat4'
    event_data = collect_event_data(path)

    # Step 2: Event Processing
    # Preprocess the event data and convert it into a spatial-temporal representation (event frames)
    max_x = event_data['x'].max().astype(int) + 1
    max_y = event_data['y'].max().astype(int) + 1
    # Use single polarity only for visualisation purposes
    polarity = 2 #polarity channel
    sensor_size = (max_x, max_y, 2)
    max_ts = event_data['t'].max() #(*10^6s)
    time_wnd_frames=50000 #micorseconds (*10^3ms)
    animFLAG = False
    eventframes = preprocess_event_data(sensor_size, time_wnd_frames, event_data, animFLAG)
    eventframes = torch.sum(eventframes, dim=1, keepdim=True)
    eventframes = eventframes[0:1,0,:,:]
    # plt.imshow(eventframes[0,0,:,:])

    # Step 3: Gaussian Multivariate Distribution Bank
    # Define a bank of Gaussian distributions with different orientations
    fltsize=50
    size = (fltsize, fltsize)
    sigma_x = fltsize/4
    sigma_y = fltsize/8
    # number of angles, please choose an even number
    numangles=6
    angles = np.round(np.linspace(0, 180, numangles)).astype(int)
    show_imgs = False
    bankMVG = bank_MVG(size, sigma_x, sigma_y, angles,show_imgs, numangles)


    # # Step 4: Convolution and Visualization
    # # Convolve the event map with each Gaussian distribution from the bank and visualize the results
    maps = torch.empty((len(eventframes),sensor_size[1], sensor_size[0]))
    for kernel in range(0, len(bankMVG)):
        for frame in range(0, len(eventframes)):
            print('convolving kernel ' + str(kernel) + ' frame ' + str(frame) + ' of '+ str(len(eventframes)))
            convolved_map=torch.from_numpy(conv_vis(eventframes[frame,0,:,:], bankMVG[kernel]))
            maps[frame,:,:]=convolved_map
        finalmap=torch.sum(maps, dim=0, keepdim=True)
        max_val=finalmap.max()
        plt.imshow(finalmap[0,:,:])
        plt.imsave('results/img'+str(angles[kernel])+'.png', finalmap[0,:,:])

    # Example usage
    angles = np.array([0, 45, 90, 135])  # Edge orientations in degrees
    activations = np.array([0.7, 0.2, 0.5, 0.4])  # Neuronal activations
    threshold = 30  # Threshold for considering angles close enough