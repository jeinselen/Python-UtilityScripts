# -------------------------------
# Image Weighted Collage v0.1
# Input: folder of png or jpg images
# Output: single image with physics based centre packing
# -------------------------------

from PIL import Image, ImageDraw
import random
import math
import os

# -------------------------------
# Parameters
# -------------------------------

# Input / output
INPUT_DIRECTORY = "collage"
OUTPUT_FILE = "collage-#.png"	# Pound sign will be replaced with sort type

# General layout
TARGET_SIZE = (4096, 4096)		# Final output image size
MARGIN_DISTANCE = 8				# Space between images
INITIAL_RADIUS = 512			# Initial layout
MAX_INITIAL_DIM = 512			# Maximum starting size
SORT_TYPE = "RANDOM"			# NONE, AREA, WIDTH, HEIGHT, RANDOM
RANDOM_COUNT = 25				# Number of generations to attempt (enabled when sort is random)

# Scale to fit
SCALE_FACTOR = 0.95				# Amount to scale each time
MAX_SCALE_DOWN = 0.75			# Minimum scale
MAX_RESCALE_ATTEMPTS = 16		# Scale iterations

# Physics simulation
MAX_MOVEMENT_PER_ITER = 128.0	# Maximum distance to move each time
REPULSION_STRENGTH = 10.0		# Image overlap avoidance
ATTRACTION_RATE = (0.0001, 0.001)	# XY attraction rate
ATTRACTION_WEIGHT = 0.0001		# Weight attraction by image area
RELAXATION_ITERATIONS = 4096	# Movement iterations



# -------------------------------
# Variables
# -------------------------------

CENTER = (TARGET_SIZE[0] // 2, TARGET_SIZE[1] // 2)



# -------------------------------
# Functions
# -------------------------------

def load_images(image_paths):
	nodes = []
	for path in image_paths:
		img = Image.open(path).convert("RGBA")
		w, h = img.size
		nodes.append({
			'image': img,
			'orig_width': w,
			'orig_height': h,
			'width': w,
			'height': h,
			'scale': 1.0,
			'fixed': False
		})
	return nodes



def initial_rescale(nodes):
	"""Rescale large images so that none exceed MAX_INITIAL_DIM in width or height."""
	for n in nodes:
		if n['width'] > MAX_INITIAL_DIM or n['height'] > MAX_INITIAL_DIM:
			# Determine scale
			scale_w = MAX_INITIAL_DIM / n['width']
			scale_h = MAX_INITIAL_DIM / n['height']
			scale = min(scale_w, scale_h)
			# Apply scaling
			n['scale'] = scale
			n['width'] = int(n['orig_width'] * scale)
			n['height'] = int(n['orig_height'] * scale)



def sort_by_area(nodes):
	return sorted(nodes, key=lambda n: n['width']*n['height'], reverse=True)

def sort_by_width(nodes):
	return sorted(nodes, key=lambda n: n['width'], reverse=True)

def sort_by_height(nodes):
	return sorted(nodes, key=lambda n: n['height'], reverse=True)



def place_initial(nodes):
	nodes[0]['x'] = CENTER[0]
	nodes[0]['y'] = CENTER[1]
	nodes[0]['fixed'] = True
	
	# Place others in a rough circle
	num = len(nodes)
	angle_step = 6*math.pi/(max(1, (num-1)))
	for i, node in enumerate(nodes[1:], start=1):
		angle = angle_step * (i-1)
		x = CENTER[0] + INITIAL_RADIUS * math.cos(angle)
		y = CENTER[1] + INITIAL_RADIUS * math.sin(angle)
		node['x'] = x
		node['y'] = y



def bounding_box(node):
	x1 = node['x'] - node['width']/2
	y1 = node['y'] - node['height']/2
	x2 = node['x'] + node['width']/2
	y2 = node['y'] + node['height']/2
	return (x1, y1, x2, y2)



def boxes_overlap(b1, b2, margin=MARGIN_DISTANCE):
	return not (b1[2] + margin < b2[0] or b2[2] + margin < b1[0] or
b1[3] + margin < b2[1] or b2[3] + margin < b1[1])



def apply_forces(nodes):
	for i, n1 in enumerate(nodes):
		if n1['fixed']:
			continue
		force_x, force_y = 0.0, 0.0
		b1 = bounding_box(n1)
		scale = ((b1[2] - b1[0]) * (b1[3] - b1[1])) / TARGET_SIZE[0]
		
		# Repulsion from other images
		for j, n2 in enumerate(nodes):
			if i == j:
				continue
			b2 = bounding_box(n2)
			if boxes_overlap(b1, b2):
				dx = n1['x'] - n2['x']
				dy = n1['y'] - n2['y']
				dist = math.sqrt(dx*dx + dy*dy) + 0.1
				factor = REPULSION_STRENGTH * (1.0/dist)
				force_x += dx * factor
				force_y += dy * factor
		
		# Attraction to center
		dx_center = CENTER[0] - n1['x']
		dy_center = CENTER[1] - n1['y']
		force_x += dx_center * (ATTRACTION_RATE[0] + (scale * ATTRACTION_WEIGHT))
		force_y += dy_center * (ATTRACTION_RATE[1] + (scale * ATTRACTION_WEIGHT))
		
		# Limit movement
		dist_move = math.sqrt(force_x*force_x + force_y*force_y)
		if dist_move > MAX_MOVEMENT_PER_ITER:
			scale = MAX_MOVEMENT_PER_ITER/dist_move
			force_x *= scale
			force_y *= scale
		
		n1['x'] += force_x
		n1['y'] += force_y



def attempt_rescale(nodes):
	changed = False
	for i, n1 in enumerate(nodes):
		for j, n2 in enumerate(nodes):
			if i >= j:
				continue
			b1 = bounding_box(n1)
			b2 = bounding_box(n2)
			if boxes_overlap(b1, b2):
				# Scale down the smaller image
				if n1['width']*n1['height'] < n2['width']*n2['height']:
					smaller = n1
				else:
					smaller = n2
				new_scale = smaller['scale'] * SCALE_FACTOR
				if new_scale >= MAX_SCALE_DOWN:
					smaller['scale'] = new_scale
					smaller['width'] = int(smaller['orig_width'] * new_scale)
					smaller['height'] = int(smaller['orig_height'] * new_scale)
					changed = True
	return changed



def run_relaxation(nodes):
	for iteration in range(RELAXATION_ITERATIONS):
		apply_forces(nodes)
		if iteration % 20 == 0:
			for attempt in range(MAX_RESCALE_ATTEMPTS):
				if not attempt_rescale(nodes):
					break



def compose_final_image(nodes):
	min_x, min_y = float('inf'), float('inf')
	max_x, max_y = float('-inf'), float('-inf')
	
	for n in nodes:
		b = bounding_box(n)
		min_x = min(min_x, b[0])
		min_y = min(min_y, b[1])
		max_x = max(max_x, b[2])
		max_y = max(max_y, b[3])
		
	width = int(max_x - min_x)
	height = int(max_y - min_y)
	
	canvas = Image.new("RGBA", (width, height), (255,255,255,0))
	for n in nodes:
		x1 = int(n['x'] - n['width']/2 - min_x)
		y1 = int(n['y'] - n['height']/2 - min_y)
		resized = n['image'].resize((n['width'], n['height']), Image.LANCZOS)
		canvas.alpha_composite(resized, (x1, y1))
	
	scale_to_target = min(TARGET_SIZE[0]/width, TARGET_SIZE[1]/height)
	if scale_to_target < 1.0:
		new_w = int(width*scale_to_target)
		new_h = int(height*scale_to_target)
		canvas = canvas.resize((new_w, new_h), Image.LANCZOS)
	
	return canvas



if __name__ == "__main__":
	image_folder = INPUT_DIRECTORY
	image_paths = [os.path.join(image_folder, f) for f in os.listdir(image_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
	count = RANDOM_COUNT if SORT_TYPE == "RANDOM" else 1
	
	for x in range(count):
		# Generate file name
		if count > 1:
			output = OUTPUT_FILE.replace("#", SORT_TYPE.lower()+str(x + 1))
		else:
			output = OUTPUT_FILE.replace("#", SORT_TYPE.lower())
		
		# Load image files
		nodes = load_images(image_paths)
		
		# Downsample large images
		initial_rescale(nodes)
		
		# Sort or randomise
		if SORT_TYPE == "AREA":
			nodes = sort_by_area(nodes)
		elif SORT_TYPE == "WIDTH":
			nodes = sort_by_width(nodes)
		elif SORT_TYPE == "HEIGHT":
			nodes = sort_by_height(nodes)
		elif SORT_TYPE == "RANDOM":
			nodes = random.sample(nodes, len(nodes))
		
		# Initial layout of elements
		place_initial(nodes)
		
		# Pseudo physics simulation
		run_relaxation(nodes)
		
		# Create and save final image
		final_image = compose_final_image(nodes)
		final_image.save(output)
		print("Saved "+output)
	else:
		print("Process completed")