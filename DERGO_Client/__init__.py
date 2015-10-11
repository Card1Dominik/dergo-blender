
import bpy
import bgl
import mathutils
import time

from .mesh_export import MeshExport
from .network import  *

bl_info = {
	 "name": "DERGO3D",
	 "author": "Matías N. Goldberg",
	 "version": (2, 1),
	 "blender": (2, 76, 0),
	 "category": "Render",
	 "location": "Info header, render engine menu",
	 "warning": "",
	 "wiki_url": "",
	 "tracker_url": "",
	 "description": "OGRE3D integration for Blender"
}

class DergoRenderEngine(bpy.types.RenderEngine):
	# These three members are used by blender to set up the
	# RenderEngine; define its internal name, visible name and capabilities.
	bl_idname = 'DERGO3D'
	bl_label = 'OGRE3D Renderer'
	bl_use_preview = True
	# We need this set to True so that DergoRenderEngine isn't restarted while we animate.
	bl_use_shading_nodes = True
	
	network = None
	
	objId	= 1
	meshId	= 1
	
	def __init__(self):
		print( "Reinit" )
		
	def __del__(self):
		print( "Deinit" )
		
	def bake(self, scene, obj, pass_type, object_id, pixel_array, num_pixels, depth, result):
		return
	def update_script_node(self, node):
		return

	# This is the only method called by blender, in this example
	# we use it to detect preview rendering and call the implementation
	# in another method.
	def render(self, scene):
		scale = scene.render.resolution_percentage / 100.0
		self.size_x = int(scene.render.resolution_x * scale)
		self.size_y = int(scene.render.resolution_y * scale)

		print( self.is_preview )

		#if scene.name == 'preview':
		if self.is_preview:
			self.render_preview(scene)
		else:
			self.render_scene(scene)

	# In this example, we fill the preview renders with a flat green color.
	def render_preview(self, scene):
		pixel_count = self.size_x * self.size_y

		# The framebuffer is defined as a list of pixels, each pixel
		# itself being a list of R,G,B,A values
		green_rect = [[0.0, 1.0, 0.0, 1.0]] * pixel_count

		# Here we write the pixel values to the RenderResult
		result = self.begin_result(0, 0, self.size_x, self.size_y)
		result.layers[0].passes[0].rect = green_rect
		self.end_result(result)

	# In this example, we fill the full renders with a flat blue color.
	def render_scene(self, scene):
		pixel_count = self.size_x * self.size_y

		# The framebuffer is defined as a list of pixels, each pixel
		# itself being a list of R,G,B,A values
		blue_rect = [[0.2, 0.4, 6.0, 1.0]] * pixel_count

		# Here we write the pixel values to the RenderResult
		result = self.begin_result(0, 0, self.size_x, self.size_y)
		result.layers[0].passes[0].rect = blue_rect
		self.end_result(result)
		
	def reset( self ):
		# Tell server to reset
		self.network.sendData( FromClient.Reset, None )
		# Remove our data
		for object in bpy.data.objects:
			try:
				del object['DERGO']
			except KeyError: pass
		for mesh in bpy.data.meshes:
			try:
				del mesh['DERGO']
			except KeyError: pass

		self.objId	= 1
		self.meshId	= 1
		
	def view_update(self, context):
		if not self.network:
			self.network = Network()
			self.network.connect()
			self.reset()
	
		scene = context.scene
		
		for object in scene.objects:
			if object.type == 'MESH':
				self.syncItem( object, scene )
		return
	
	def syncItem( self, object, scene ):
		#if object.is_visible( scene ):
		if 'DERGO' not in object:
			object['DERGO'] = { 'in_sync' : False, 'id' : self.objId, 'id_mesh' : 0 }
			self.objId += 1

		objDergoProps = object['DERGO']

		# Server doesn't have object, or object was moved, or
		# mesh was modified, or modifier requires an update.
		#	print( object.is_updated_data )	# True when skeleton moved
		#	print( object.data.is_updated )	# False when skeleton moved
		if not objDergoProps['in_sync'] or object.is_updated or object.is_updated_data:
			if 'DERGO' not in object.data:
				object.data['DERGO'] = { 'in_sync' : False, 'id' : self.meshId }
				self.meshId += 1
				
			dataDergoProps = object.data['DERGO']
			
			if len( object.modifiers ) > 0:
				meshName = '##internal##_' + object.name
				linkedMeshId = objDergoProps['id'] | 0x8000000000000000
			else:
				meshName = object.data.name
				linkedMeshId = dataDergoProps['id']
			
			# Check if mesh changed, or if our modifiers made an update, and that
			# we haven't already sync'ed this object (only if shared)
			if \
			((not objDergoProps['in_sync'] or object.is_updated_data) and len( object.modifiers ) > 0) or \
			((not dataDergoProps['in_sync'] or object.data.is_updated) and len( object.modifiers ) == 0):
				exportMesh = object.to_mesh( scene, True, "PREVIEW", True, False)
					
				# Triangulate mesh and remap vertices to eliminate duplicates.
				materialTable = []
				exportVertexArray = MeshExport.DeindexMesh(exportMesh, materialTable)
				#triangleCount = len(materialTable)
				
				dataToSend = bytearray( struct.pack( '=Q', linkedMeshId ) )
				nameAsUtfBytes = meshName.encode('utf-8')
				dataToSend.extend( struct.pack( '=I', len( nameAsUtfBytes ) ) )
				dataToSend.extend( nameAsUtfBytes )
				dataToSend.extend( struct.pack( "=IBB", len( exportVertexArray ),
												len(exportMesh.tessface_vertex_colors) > 0,
												len(exportMesh.tessface_uv_textures) ) )
				dataToSend.extend( MeshExport.vertexArrayToBytes( exportVertexArray ) )
				dataToSend.extend( struct.pack( '=%sH' % len( materialTable ), *materialTable ) )
				
				self.network.sendData( FromClient.Mesh, dataToSend )
				bpy.data.meshes.remove( exportMesh )
				if len( object.modifiers ) == 0:
					dataDergoProps['in_sync'] = True
			
			# Item is now linked to a different mesh! Remove ourselves			
			if objDergoProps['id_mesh'] != 0 and objDergoProps['id_mesh'] != linkedMeshId:
				self.network.sendData( FromClient.ItemRemove, struct.pack( '=QQ', objDergoProps['id_mesh'], objDergoProps['id'] ) )
				objDergoProps['in_sync'] = False

			# Keep it up to date.
			objDergoProps['id_mesh'] = linkedMeshId

			# Create or Update Item.
			if not objDergoProps['in_sync'] or object.is_updated:
				# Mesh ID & Item ID
				dataToSend = bytearray( struct.pack( '=QQ', linkedMeshId, objDergoProps['id'] ) )
				
				# Item name
				asUtfBytes = object.data.name.encode('utf-8')
				dataToSend.extend( struct.pack( '=I', len( asUtfBytes ) ) )
				dataToSend.extend( asUtfBytes )
				
				loc, rot, scale = object.matrix_world.decompose()
				dataToSend.extend( struct.pack( '=10f', loc[0], loc[1], loc[2],\
														rot[0], rot[1], rot[2], rot[3],\
														scale[0], scale[1], scale[2] ) )
				
				self.network.sendData( FromClient.Item, dataToSend )

			objDergoProps['in_sync'] = True
		
	def view_draw(self, context):
		invViewProj = context.region_data.perspective_matrix.inverted()
		camPos = invViewProj * mathutils.Vector( (0, 0, 0, 1 ) )
		camPos /= camPos[3]
		
		camUp = invViewProj * mathutils.Vector( (0, 1, 0, 1 ) )
		camUp /= camUp[3]
		camUp -= camPos
		
		camRight = invViewProj * mathutils.Vector( (1, 0, 0, 1 ) )
		camRight /= camRight[3]
		camRight -= camPos
		
		camForwd = invViewProj * mathutils.Vector( (0, 0, -1, 1 ) )
		camForwd /= camForwd[3]
		camForwd -= camPos
		
		# print( 'Pos ' + str(camPos) )
		# print( 'Up ' + str(camUp) )
		# print( 'Right ' + str(camRight) )
		# print( 'Forwd ' + str(camForwd) )
		# return
		
		size_x = int(context.region.width)
		size_y = int(context.region.height)
		
		self.renderedView = False
		self.network.sendData( FromClient.Render,\
			struct.pack( '=15fBHH', context.area.spaces[0].lens,\
						context.area.spaces[0].clip_start,\
						context.area.spaces[0].clip_end,\
						camPos[0], camPos[1], camPos[2],\
						camUp[0], camUp[1], camUp[2],\
						camRight[0], camRight[1], camRight[2],\
						camForwd[0], camForwd[1], camForwd[2],\
						context.region_data.is_perspective,\
						size_x, size_y ) )
		
		while not self.renderedView:
			self.network.receiveData( self )
		#context.area.tag_redraw()
		
	def processMessage( self, header_sizeBytes, header_messageType, data ):
		if header_messageType == FromServer.Result:
			self.renderedView = True
			resolution = struct.unpack_from( '=HH', memoryview( data ) )
			imageSizeBytes = resolution[0] * resolution[1] * 4
			glBuffer = bgl.Buffer(bgl.GL_BYTE, [imageSizeBytes], list(data[4:4+imageSizeBytes]))
			bgl.glRasterPos2i(0, 0)
			bgl.glDrawPixels( resolution[0], resolution[1], bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, glBuffer )
		
def get_panels():
	return (
		bpy.types.RENDER_PT_render,
		bpy.types.RENDER_PT_output,
		bpy.types.RENDER_PT_encoding,
		bpy.types.RENDER_PT_dimensions,
		bpy.types.RENDER_PT_stamp,
		bpy.types.SCENE_PT_scene,
		bpy.types.SCENE_PT_audio,
		bpy.types.SCENE_PT_unit,
		bpy.types.SCENE_PT_keying_sets,
		bpy.types.SCENE_PT_keying_set_paths,
		bpy.types.SCENE_PT_physics,
		bpy.types.WORLD_PT_context_world,
		bpy.types.DATA_PT_context_mesh,
		bpy.types.DATA_PT_context_camera,
		bpy.types.DATA_PT_context_lamp,
		bpy.types.DATA_PT_texture_space,
		bpy.types.DATA_PT_curve_texture_space,
		bpy.types.DATA_PT_mball_texture_space,
		bpy.types.DATA_PT_vertex_groups,
		bpy.types.DATA_PT_shape_keys,
		bpy.types.DATA_PT_uv_texture,
		bpy.types.DATA_PT_vertex_colors,
		bpy.types.DATA_PT_camera,
		bpy.types.DATA_PT_camera_display,
		bpy.types.DATA_PT_lens,
		bpy.types.DATA_PT_custom_props_mesh,
		bpy.types.DATA_PT_custom_props_camera,
		bpy.types.DATA_PT_custom_props_lamp,
		bpy.types.TEXTURE_PT_clouds,
		bpy.types.TEXTURE_PT_wood,
		bpy.types.TEXTURE_PT_marble,
		bpy.types.TEXTURE_PT_magic,
		bpy.types.TEXTURE_PT_blend,
		bpy.types.TEXTURE_PT_stucci,
		bpy.types.TEXTURE_PT_image,
		bpy.types.TEXTURE_PT_image_sampling,
		bpy.types.TEXTURE_PT_image_mapping,
		bpy.types.TEXTURE_PT_musgrave,
		bpy.types.TEXTURE_PT_voronoi,
		bpy.types.TEXTURE_PT_distortednoise,
		bpy.types.TEXTURE_PT_voxeldata,
		bpy.types.TEXTURE_PT_pointdensity,
		bpy.types.TEXTURE_PT_pointdensity_turbulence,
		bpy.types.PARTICLE_PT_context_particles,
		bpy.types.PARTICLE_PT_emission,
		bpy.types.PARTICLE_PT_hair_dynamics,
		bpy.types.PARTICLE_PT_cache,
		bpy.types.PARTICLE_PT_velocity,
		bpy.types.PARTICLE_PT_rotation,
		bpy.types.PARTICLE_PT_physics,
		bpy.types.PARTICLE_PT_boidbrain,
		bpy.types.PARTICLE_PT_render,
		bpy.types.PARTICLE_PT_draw,
		bpy.types.PARTICLE_PT_children,
		bpy.types.PARTICLE_PT_field_weights,
		bpy.types.PARTICLE_PT_force_fields,
		bpy.types.PARTICLE_PT_vertexgroups,
		bpy.types.PARTICLE_PT_custom_props,
		)
		
def register():
	bpy.utils.register_class(DergoRenderEngine)
	
	# RenderEngines also need to tell UI Panels that they are compatible
	# Otherwise most of the UI will be empty when the engine is selected.
	# In this example, we need to see the main render image button and
	# the material preview panel.
	#from bl_ui import properties_render
	#properties_render.RENDER_PT_render.COMPAT_ENGINES.add('DERGO3D')
	#del properties_render

	#from bl_ui import properties_material
	#properties_material.MATERIAL_PT_preview.COMPAT_ENGINES.add('DERGO3D')
	#del properties_material
	for panel in get_panels():
		panel.COMPAT_ENGINES.add('DERGO3D')

def unregister():
	bpy.utils.unregister_class(DergoRenderEngine)

	for panel in get_panels():
		panel.COMPAT_ENGINES.remove('DERGO3D')