
# The minimum distances between cores.
minimum_core_distance = 42
# How often do we try to place a core, anyways?
core_offset = 2
# How much do we want to damp the noise to create chunks that are similar to each other next to each other?
# 1 creates basically no chunks. 0 doesn't work.
noise_damping_factor = 0.025
# This is used to select a sprite from the output of OpenSimplex noise, normalized between 0 and 1.
terrain_sprite_bins = [0, 0.2, 0.25, 0.5, 0.55, 0.6, 0.7, 0.8, 0.825, 0.875, 0.9, 0.915, 0.25, 1.0]
