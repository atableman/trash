import sublime
from sublime import Region
from sublime_plugin import WindowCommand, TextCommand, EventListener
from .show import show, refresh_sym_view, get_sidebar_views_groups, get_sidebar_status

class OutlineCommand(WindowCommand):
	def run(self, immediate=False, single_pane=False, project=False, other_group=False, layout=0):
		show(self.window, single_pane=single_pane, other_group=other_group, layout=layout)

class OutlineCloseSidebarCommand(WindowCommand):
	def run(self):
		for v in self.window.views():
			if u'𝌆' in v.name():
				self.window.focus_view(v)
				self.window.run_command('close_file')

		self.window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

class OutlineRefreshCommand(TextCommand):
	def run(self, edit, symlist=None, symkeys=None, path=None, to_expand=None, toggle=None):
		self.view.erase(edit, Region(0, self.view.size()))
		self.view.insert(edit, 0, "\n".join(symlist))
		self.view.settings().set('symlist', symlist)
		self.view.settings().set('symkeys', symkeys)
		self.view.settings().set('current_row', -1)
		self.view.settings().set('current_file', path)
		self.view.sel().clear()

class OutlineEventHandler(EventListener):

	# Called when the user clicks on a row in the outline.
	def on_outline_selection_modified(self, view):
		if 'outline.hidden-tmLanguage' not in view.settings().get('syntax'):
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		sym_view = view
		window = view.window()
		sym_group, i = window.get_view_index(sym_view)
			
		if len(sym_view.sel()) == 0:
			return

		(row, col) = sym_view.rowcol(sym_view.sel()[0].begin())

		active_view =None
		for group in range(window.num_groups()):
			if group != sym_group and group != fb_group:
				active_view = window.active_view_in_group(group)
		if active_view != None:
			# In addition to preventing unneeded work, the following 'if'
			#	has a more important function. It stops ping-pong
			#	event firing that can occur (e.g. prevents what
			#	happens when we update the highlighted row in the outline 
			#	as the user moves in the text. When the highlighted outline 
			#	row is updated it, in turn, fires the same event to update 
			# 	the cursor position in the text etc..) The 'if' statement
			#	prevents this 2nd event from cascading.
			if sym_view.settings().get('current_row') == row:
				return
			region_position = sym_view.settings().get('symkeys')[row]
			r = Region(region_position[0], region_position[1])
			active_view.show_at_center(r)
			active_view.sel().clear()
			active_view.sel().add(r)
			sym_view.settings().set('current_row',row)
			window.focus_view(active_view)

	def on_activated(self, view):
		if u'𝌆' in view.name():
			return
		# Avoid error message when console opens, as console is also a view, albeit with a group index of -1
		if view.window().get_view_index(view)[0] == -1:
			return

		if not get_sidebar_status(view):
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		if sym_view != None:
			if sym_view.settings().get('current_file') == view.file_name() and view.file_name() != None:
				return
			else:
				sym_view.settings().set('current_file', view.file_name())
			
		symlist = view.get_symbols()
		if sym_view is not None:
			sym_view.settings().set('color_scheme', view.settings().get('color_scheme'))
		refresh_sym_view(sym_view, symlist, view.file_name())
		self.update_outline_selection_from_text_section(view, sym_view, sym_group, fb_view, fb_group)

	# called as the user updates the cursor position with the text. As the user navigates through the text,
	#	This routine updates which row is highlighted in the outline.
	#	It is also called when the user switches between files ('on_activated') and after saving ('on_pre_save')
	def update_outline_selection_from_text_section( self, view, sym_view, sym_group, fb_view, fb_group, activated=True ):
		##if sym_view.settings().get("do_not_update_source_view"):
		##	return
		window = view.window()
		if sym_view == None:
			return
		if window == None:
			return	
		current_file_name = sym_view.settings().get('current_file')
		active_view =None
		for group in range(window.num_groups()):
			if group != sym_group and group != fb_group:
				active_view = window.active_view_in_group(group)
			if active_view != None:
				if view.file_name() == current_file_name:		# active_view!?!?
					selections_in_view = view.sel()
					if len(selections_in_view) > 0:
						selection_point = selections_in_view[0].begin()
						selection_row = self.get_outline_row_for_text_selection(sym_view, selection_point )
						if selection_row == sym_view.settings().get("current_row"):
							return
						if selection_row > -1:
							# set a flag on the outline pane's state to prevent the outline
							#	from trying to update the text buffer's state when we set the outline's state.
							##sym_view.settings().set("do_not_update_source_view", True)
							sym_view.settings().set("current_row", selection_row)
							sym_view.run_command("goto_line", {"line": selection_row + 1} )
							window.focus_view(view)
							##sym_view.settings().erase("do_not_update_source_view")

	# helper function used in 'update_outline_selection_from_text_section'
	def get_outline_row_for_text_selection(self, sym_view,source_row):
		ranges = sym_view.settings().get("symkeys")
		num_outline_entries = len(ranges)
		if num_outline_entries == 0:
			return -1
		for x in range(num_outline_entries-1):
			if source_row > ranges[x][0]:
				if source_row < ranges[x+1][1]:
					return x
		if source_row > ranges[-1][0]:
			return len(ranges) - 1
		if source_row < ranges[0][0]:
			return 0
		return -1

	# The actual event handler. It calls either 'update_outline_selection_from_text_section'
	#	or 'on_outline_selection_modified' as appropriate.
	def on_selection_modified(self, view):
		# following 3 lines prevent some errors in 'get_sidebar_views_groups' 
		#	where window can be None as the user clicks around. Not sure why this happens
		#	and it's not a huge problem, but better to not throw exceptions for no reason.
		window = view.window()
		if window is None:
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		if sym_view is None:
			return
		
		#window = view.window()
		sym_group, i = window.get_view_index(view)

		if len(view.sel()) == 0:
			return
		if sym_view.id() == view.id():
			self.on_outline_selection_modified(view)
			pass
		else:
			self.update_outline_selection_from_text_section(view, sym_view, sym_group, fb_view, fb_group)
			return
			
			current_file_name = view.settings().get('current_file')
			active_view =None
			for group in range(window.num_groups()):
				if group != sym_group and group != fb_group:
					active_view = window.active_view_in_group(group)
				if active_view != None:
					if active_view.file_name() == current_file_name:
						selection_point = view.sel()[0].begin()
						selection_row = self.get_outline_row_for_text_selection(sym_view, selection_point )
						# don't update the outline if we are still within the same symbol
						if selection_row == sym_view.settings().get("current_row"):
							return
						if selection_row > -1:
							sym_view.settings().set("current_row", selection_row)
							sym_view.run_command("goto_line", {"line": selection_row + 1} )
							window.focus_view(view)
				pass
			
		

	def on_pre_save(self, view):
		if u'𝌆' in view.name():
			return
		# this is not absolutely necessary, and prevents views that do not have a file reference from displaying 
		# the symbol list
		# but it solves a console error if the console is activiated, as console is also a view....
		if view.file_name() == None:
			return

		if not get_sidebar_status(view):
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		if sym_view != None:
			# Note here is the only place that differs from on_activate_view
			if sym_view.settings().get('current_file') != view.file_name():
				sym_view.settings().set('current_file', view.file_name())
		
		symlist = view.get_symbols()

		refresh_sym_view(sym_view, symlist, view.file_name())
		self.update_outline_selection_from_text_section(view, sym_view, sym_group, fb_view, fb_group)