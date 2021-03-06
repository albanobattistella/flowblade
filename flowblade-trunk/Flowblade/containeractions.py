"""
    Flowblade Movie Editor is a nonlinear video editor.
    Copyright 2012 Janne Liljeblad.

    This file is part of Flowblade Movie Editor <http://code.google.com/p/flowblade>.

    Flowblade Movie Editor is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Flowblade Movie Editor is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Flowblade Movie Editor. If not, see <http://www.gnu.org/licenses/>.
"""

import hashlib
import subprocess
import sys
import threading
import time

import appconsts
from editorstate import PROJECT
import gmicheadless
import respaths
import userfolders

FULL_RENDER = 0
CLIP_RENDER = 1

_status_polling_thread = None

# ----------------------------------------------------- interface
def get_action_object(clip):
    if clip.container_data.container_type == appconsts.CONTAINER_CLIP_GMIC:
        return GMicContainerActions(clip)

def shutdown_polling():
    if _status_polling_thread == None:
        return
    
    _status_polling_thread.shutdown()
                

# ---------------------------------------------------- action objects
class AbstractContainerActionObject:
    
    def __init__(self, clip):
        self.clip = clip
        self.container_data = clip.container_data

    def render_full_media(self):
        print("AbstractContainerActionObject.render_full_media not impl")

    def get_rendered_media_dir(self):
        return self.get_container_clips_dir() + "/" + self.get_container_program_id()

    def get_container_program_id(self):
        id_md_str = str(self.container_data.container_type) + self.container_data.program + self.container_data.unrendered_media
        return hashlib.md5(id_md_str.encode('utf-8')).hexdigest()

    def get_container_clips_dir(self):
        return userfolders.get_data_dir() + appconsts.CONTAINER_CLIPS_DIR

    def add_as_status_polling_object(self):
        global _status_polling_thread
        if _status_polling_thread == None:
            _status_polling_thread = ContainerStatusPollingThread()
            _status_polling_thread.start()
                   
        _status_polling_thread.poll_objects.append(self)

    def remove_as_status_polling_object(self):
        _status_polling_thread.poll_objects.remove(self)
    
    def update_render_status(self):
        print("AbstractContainerActionObject.update_render_status not impl")

    def abort_render(self):
        print("AbstractContainerActionObject.abort_render not impl")
    


class GMicContainerActions(AbstractContainerActionObject):

    def __init__(self, clip):
        AbstractContainerActionObject.__init__(self, clip)
        self.render_type = -1 # to be set below

    def render_full_media(self):
        print("render full media")
        self.render_type = FULL_RENDER
        self._launch_render(0, self.container_data.unrendered_length)

        self.add_as_status_polling_object()

    def _launch_render(self, range_in, range_out):
        print("rendering gmic container clip:", self.get_container_program_id(), range_in, range_out)
        gmicheadless.clear_flag_files(self.get_container_program_id())
        
        
        args = ("session_id:" + self.get_container_program_id(), 
                "script:" + self.container_data.program,
                "clip_path:" + self.container_data.unrendered_media,
                "range_in:" + str(range_in),
                "range_out:"+ str(range_out),
                "profile_desc:" + PROJECT().profile.description().replace(" ", "_"))

        # Run with nice to lower priority if requested
        nice_command = "nice -n " + str(10) + " " + respaths.LAUNCH_DIR + "flowbladegmicheadless"
        for arg in args:
            nice_command += " "
            nice_command += arg

        subprocess.Popen([nice_command], shell=True)

    def update_render_status(self):
        if gmicheadless.session_render_complete(self.get_container_program_id()) == True:
            self.remove_as_status_polling_object()
            if self.render_type == FULL_RENDER:
                # "old_clip", "new_clip", "track", "index"
                data = {"old_clip":self.clip,
                        "new_clip":rendered_clip,
                        "track":track,
                        "index":clip_index}
                action = edit.container_clip_full_render_replace(data)
                action.do_edit()

        else:
            status = gmicheadless.get_session_status(self.get_container_program_id())
            if status != None:
                print(status)
            else:
                print("Miss")

    def abort_render(self):
        print("AbstractContainerActionObject.abort_render not impl")


        
class ContainerStatusPollingThread(threading.Thread):
    
    def __init__(self):
        self.poll_objects = []
        self.abort = False
        #self.running = False
        threading.Thread.__init__(self)

    def run(self):
        #self.running = True
        
        while self.abort == False:
            for poll_obj in self.poll_objects:
                poll_obj.update_render_status()
                    
                
            time.sleep(1.0)
            

    def shutdown(self):
        for poll_obj in self.poll_objects:
            poll_obj.abort_render()
        
        self.abort = True
        
