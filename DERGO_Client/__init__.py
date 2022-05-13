
import bpy
import bgl
import mathutils
import time

from .ui_hdr import *
from .ui import *
from .mesh_export import MeshExport
from .network import  *
from .engine import *
from .export_to_file import *
from .instant_radiosity import *
from .mesh_export import *
from .properties import *

bl_info = {
	 "name": "DERGO3D",
	 "author": "Matías N. Goldberg",
	 "version": (2, 1),
	 "blender": (2, 93, 0),
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
	bl_use_preview = False
	# We need this set to True so that DergoRenderEngine isn't restarted while we animate.
	bl_use_shading_nodes = True
	
	def __init__(self):
		print( "Reinit" )
		#self.initialized = False
		if not engine.dergo:
			engine.dergo = engine.Engine()
		engine.Engine.numActiveRenderEngines += 1
		self.needsReset = False
		if engine.Engine.numActiveRenderEngines == 1:
			self.needsReset = True
		
	def __del__(self):
		print( "Deinit" )
		if engine.dergo is not None and engine.Engine.numActiveRenderEngines > 0:
			engine.Engine.numActiveRenderEngines -= 1
		
	#def bake(self, scene, obj, pass_type, object_id, pixel_array, num_pixels, depth, result):
	def bake(self, depsgraph, object, pass_type, pass_filter, width, height):
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
		
	def view_update(self, context, depsgraph):
		if self.needsReset:
			engine.dergo.reset()
			self.needsReset = False

		engine.dergo.view_update( context )
		return
		
	def view_draw(self, context, depsgraph):
		if ui.isInDummyMode( context ):
			return

		self.renderedView = False
		
		size_x = int(context.region.width)
		size_y = int(context.region.height)
		engine.dergo.sendViewRenderRequest( context, context.area, context.region_data,\
											True, size_x, size_y )
		
		while not self.renderedView:
			engine.dergo.network.receiveData( self )
		#context.area.tag_redraw()

	def processMessage( self, header_sizeBytes, header_messageType, data ):
		if header_messageType == FromServer.Result:
			self.renderedView = True
			resolution = struct.unpack_from( '=HH', memoryview( data ) )
			imageSizeBytes = resolution[0] * resolution[1] * 4
			glBuffer = bgl.Buffer(bgl.GL_BYTE, [imageSizeBytes], list(data[4:4+imageSizeBytes]))
			bgl.glRasterPos2i(0, 0)
			bgl.glDrawPixels( resolution[0], resolution[1], bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, glBuffer )

	#scene['dergo']. bpy.context.window.screen.name

classes = (
	#DergoRenderEngine,
	#PbsTexture,
	#TextureMapType,
	#Engine,
	#ExportSomeData,
	#DergoWorldInstantRadiositySettings,
	Dergo_PT_world_instant_radiosity,
	#InstantRadiosity,
	#DergoObjectInstantRadiosity,
	Dergo_PT_empty_instant_radiosity,
	#ExportVertex,
	#MeshExport,
	#FromClient,
	#FromServer,
	#Network,
	#DergoWorldPccSettings,
	Dergo_PT_world_pcc,
	#ParallaxCorrectedCubemaps,
	#DergoObjectParallaxCorrectedCubemaps,
	Dergo_PT_empty_pcc,
	Dergo_PT_empty_linked_empty,
	#DergoSpaceViewSettings,
	DergoSceneSettings,
	#DergoWorldSettings,
	#DergoObjectSettings,
	#DergoMeshSettings,
	#DergoLampSettings,
	DergoMaterialSettings,
	DergoImageSettings,
	#DergoWorldShadowsSettings,
	Dergo_PT_world_shadow_settings,
	#ShadowsSettings,
	#DergoButtonsPanel,
	Dergo_PT_world,
	#AsyncPreviewOperatorToggle,
	#DummyRendererOperatorToggle,
	DergoLamp_PT_lamp,
	DergoLamp_PT_spot,
	Dergo_PT_context_material,
	Dergo_PT_material_geometry,
	#FixMaterialTexture,
	FixMeshTangents,
	Dergo_PT_material_diffuse,
	Dergo_PT_material_specular,
	Dergo_PT_material_normal,
	Dergo_PT_material_fresnel,
	Dergo_PT_material_metallic,
	#DergoDetailPanelBase,
	Dergo_PT_material_detail0,
	Dergo_PT_material_detail1,
	Dergo_PT_material_detail2,
	Dergo_PT_material_detail3,
	Dergo_PT_material_emissive,
	Dergo_PT_mesh,
	#DergoTexturePanel,
	DergoTexture_PT_context,
	DergoTexture_PT_dergo,
	DergoTexture_PT_preview,
	DergoTexture_PT_image,
	#CallbackObj,
)

#global drawHandle
def register():
	from . import properties

	engine.register()
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

	properties.register()
	ui.register()
	#ui_hdr.register()
	export_to_file.register()

	for cls in classes:
		bpy.utils.register_class(cls)

def unregister():
	from . import properties

	if bpy.context.scene.render.engine == 'DERGO3D':
		bpy.context.scene.render.engine = 'BLENDER_EEVEE'

	export_to_file.unregister()
	ui.unregister()
	properties.unregister()

	bpy.utils.unregister_class(DergoRenderEngine)

	engine.unregister()

	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)