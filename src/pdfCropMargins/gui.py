"""

Code to create and execute the GUI when that option is selected.

=========================================================================

This code evolved from the example/demo code found here:
   https://github.com/PySimpleGUI/PySimpleGUI/blob/master/DemoPrograms/Demo_PDF_Viewer.py
Below is from original module docstring:

    @created: 2018-08-19 18:00:00
    @author: (c) 2018-2019 Jorj X. McKie
    Display a PyMuPDF Document using Tkinter

    License:
    --------
    GNU GPL V3+

Copyright (C) 2019 Allen Barker (Allen.L.Barker@gmail.com)
Source code site: https://github.com/abarker/pdfCropMargins

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import sys
import os
import warnings
import textwrap
import time
import threading
import math
import io
from types import SimpleNamespace
from PIL import Image

from . import external_program_calls as ex
from .pymupdf_routines import MuPdfDocument

try:
    requires = "PySimpleGUI"
    from pdfCropMargins.vendor.pysimplegui_4_foss import PySimpleGUI as sg
    requires = "tkinter"
    import tkinter as tk
except ImportError:
    raise
    print("\nError in pdfCropMargins: The GUI feature requires {}."
          "\n\nExiting pdfcropmargins...".format(requires), file=sys.stderr)
    ex.cleanup_and_exit(1)

from .get_window_sizing_info import (get_usable_image_size, get_window_size,
                                     INITIAL_IMAGE_SIZE, FALLBACK_MAX_IMAGE_SIZE,
                                     FALLBACK_FULL_SCREEN_SIZE, parse_geometry_string)
from .main_pdfCropMargins import (process_pdf_file, parse_page_range_specifiers,
                                  parse_page_ratio_argument)

# Todo: Consider setting up so if no input file argument and the gui is used then
# the file chooser will pop up.

# Todo: It would be nice to have a resolution option for spinners, so you
# could have floats (like sliders).  Also, an increment option setting the
# increment value per click would be nice.

# Todo: If you hold the window at larger sizes until it resizes the GUI it doesn't
# resize the window when you let go.  Might be OK behavior, though...

# Uncomment for look and feel preview.
#print(sg.ListOfLookAndFeelValues())
#print(sg.LOOK_AND_FEEL_TABLE)

if ex.system_os == "Windows":
    sg.ChangeLookAndFeel("TanBlue")
    sg.theme_text_color("black")
else:
    sg.ChangeLookAndFeel("SystemDefault")

#
# Helper functions for updating the values of elements.
#

def call_all_update_funs(update_funs, values_dict):
    """Call all the functions."""
    for f in update_funs:
        f(values_dict)

def to_float_or_NA(value):
    """Convert to float unless the value is 'N/A', which is left unchanged."""
    if value == "N/A":
        return "N/A"
    else:
        return float(value)

def to_int_or_NA(value):
    """Convert to float unless the value is 'N/A', which is left unchanged."""
    if value == "N/A":
        return "N/A"
    else:
        return int(value)

def str_to_bool(string):
    """Convert a string "True" or "False" to the boolean True or False, respectively."""
    if string == "True":
        return True
    elif string == "False":
        return False
    else:
        print("Error in pdfCropMargins: String cannot be converted to bool.",
              file=sys.stderr)
        ex.cleanup_and_exit(1)

def update_value_and_return_it(input_text_element, value=None, fun_to_apply=None,
                               max_val=None, min_val=None):
    """
    1) Get the text in the `InputText` element `input_text_element`.
    2) Apply the function `fun_to_apply` to it (if one is passed in).
    3) Update the text back to the new value.

    If `value` is passed in it will be used in place of the text from step 1)."""
    if value is None:
        value = input_text_element.Get()
    if fun_to_apply:
        value = fun_to_apply(value)
    if max_val is not None and not isinstance(value, str):
        value = min(value, max_val)
    if min_val is not None and not isinstance(value, str):
        value = max(value, min_val)
    input_text_element.Update(value)
    return value

def update_combo_box(values_dict, element, element_key, args, attr, fun_to_apply):
    """Update a non-paired, independent option like `uniform`.  Function `fun_to_apply`
    is applied to the GUI value to convert it to the type `args` expects."""
    if values_dict is None:
        return
    element_value = values_dict[element_key]
    element_value = fun_to_apply(element_value)
    #element.Update(str(element_value)) # Redundant.
    setattr(args, attr, element_value)

def update_checkbox(values_dict, element, element_key, args, attr, fun_to_apply=None):
    """Update a non-paired, independent option like `uniform`.  Function `fun_to_apply`
    is applied to the GUI value to convert it to the type `args` expects."""
    if values_dict is None:
        return
    element_value = values_dict[element_key]
    if fun_to_apply:
        element_value = fun_to_apply(element_value)
    setattr(args, attr, element_value)

def update_4_values(element_list, attr, args_dict, values_dict, value_type=float,
                    max_val=None, min_val=None):
    """Update four values from a 4-value argument to argparse."""
    args_attr = args_dict[attr]

    def update_all_from_args_dict():
        for i in [0,1,2,3]:
            update_value_and_return_it(element_list[i], value=args_attr[i],
                                       max_val=max_val, min_val=min_val)

    try:
        # This comprehension is just to test that the format is correct and casts work.
        element_text4 = [str(value_type(element_list[i].Get())) for i in [0,1,2,3]]
    except ValueError:
        update_all_from_args_dict() # Replace bad text with saved version.
        return

    for i in [0,1,2,3]:
        args_attr[i] = update_value_and_return_it(element_list[i],
                                                  fun_to_apply=value_type,
                                                  max_val=max_val, min_val=min_val)

    # Update all, to convert forms like 5 to 5.0 (which were equal above).
    update_all_from_args_dict()

def update_paired_1_and_4_values(element, element_list4, attr, attr4, args_dict,
                                 values_dict, value_type=to_float_or_NA,
                                 value_type4=float, max_val=None, min_val=None):
    """Update all the value for pairs such as `percentRetain` and
    `percentRetain4`, keeping the versions with one vs. four arguments
    synchronized."""
    args_attr = args_dict[attr]
    args_attr4 = args_dict[attr4]

    def update_all_from_args_dict():
        update_value_and_return_it(element, value=args_attr[0],
                                   max_val=max_val, min_val=min_val)
        for i in [0,1,2,3]:
            update_value_and_return_it(element_list4[i], value=args_attr4[i],
                                       max_val=max_val, min_val=min_val)

    try:
        element_text = str(value_type(element.Get()))
        #element_text = str(value_type(values_dict[attr])) # Also works.
        element_text4 = [str(value_type4(element_list4[i].Get())) for i in [0,1,2,3]]
    except ValueError:
        update_all_from_args_dict() # Replace bad text with saved version.
        return
    # See if the element value changed.
    if value_type(element_text) != args_attr[0] and element_text != "N/A":
        args_attr[0] = update_value_and_return_it(element, fun_to_apply=value_type,
                                                  max_val=max_val, min_val=min_val)
        for i in [0,1,2,3]:
            args_attr4[i] = update_value_and_return_it(element_list4[i],
                                                       value=args_attr[0],
                                                       max_val=max_val, min_val=min_val)

    # See if any of the element_list4 values changed.
    elif any(value_type4(element_text4[i]) != args_attr4[i] for i in [0,1,2,3]):
        for i in [0,1,2,3]:
            args_attr4[i] = update_value_and_return_it(element_list4[i],
                                                       fun_to_apply=value_type4,
                                                       max_val=max_val, min_val=min_val)
        if len(set(args_attr4)) == 1: # All are the same value.
            args_attr[0] = update_value_and_return_it(element, value=args_attr4[0],
                                                      max_val=max_val, min_val=min_val)
        else:
            args_attr[0] = update_value_and_return_it(element, value="N/A")

    # Update all, to convert forms like 5 to 5.0 (which were equal above).
    update_all_from_args_dict()

##
## Define the buttons/events we want to handle in the event loop.
##

class Events(SimpleNamespace):
    """The events to handle in the event loop.  The class is just used as a
    namespace for holding the event tests."""
    # When no longer supporting Python2 consider making this a SimpleNamespace instance.
    def is_enter(btn):
        return btn.startswith("Return:") or btn == chr(13)

    def is_exit(btn):
        return btn == chr(27) or btn.startswith("Escape:") or btn.startswith("Exit")

    def is_crop(btn):
        return btn.startswith("Crop")

    def is_original(btn):
        return btn.startswith("Original")

    def is_next(btn):
        return btn.startswith("Next") or btn == "MouseWheel:Down" # Note mouse not giving any event.

    def is_prev(btn):
        return btn.startswith("Prior:") or btn.startswith("Prev") or btn == "MouseWheel:Up"

    def is_page_num_change(btn):
        return btn.startswith("PageNumber")

    def is_up(btn):
        return btn.startswith("Up:")

    def is_down(btn):
        return btn.startswith("Down:")

    def is_home(btn):
        return btn.startswith("Home:")

    def is_end(btn):
        return btn.startswith("End:")

    def is_left(btn):
        return btn.startswith("Left:")

    def is_right(btn):
        return btn.startswith("Right:")

    def is_zoom(btn):
        return btn.startswith("Toggle Zoom")

    def is_left_smallest_delta(btn):
        return btn.startswith("left") # Note that key is always used if set, not label.

    def is_top_smallest_delta(btn):
        return btn.startswith("top")

    def is_bottom_smallest_delta(btn):
        return btn.startswith("bottom")

    def is_right_smallest_delta(btn):
        return btn.startswith("right")

    def is_paired_single_and_quadruple_change(btn):
        return btn.startswith("uniformOrderStat")

    def is_evenodd(btn):
        return btn.startswith("evenodd")

    def is_general_checkbox_click(btn):
        # Note is_evenodd is a separate event.
        return (btn.startswith("uniform") or btn.startswith("samePageSize")
                or btn.startswith("percentText") or btn.startswith("cropSafe"))

    def is_configure(btn):
        return btn.startswith("Configure")

#
# The main function with the event loop.
#

def create_gui(input_doc_fname, fixed_input_doc_fname, output_doc_fname,
               cmd_parser, parsed_args):
    """Create a GUI for running pdfCropMargins with parsed arguments `parsed_args`
    on the PDF file named `pdf_filename`"""
    spinner_values = tuple(range(10000))

    args = parsed_args
    args_dict = {} # Dict for holding "real" values backing the GUI element values.
    update_funs = [] # A list of all the updating functions (defined below).
    bounding_box_list = None # Default to return if no crop command is called.
    delta_page_nums = None # Default to return if no crop command is called.

    ##
    ## Set up the document and window.
    ##

    document_pages = MuPdfDocument(args)
    num_pages = document_pages.open_document(fixed_input_doc_fname)
    curr_page = 0

    sg.SetOptions(tooltip_time=500)
    window_title = f"pdfCropMargins: {os.path.basename(input_doc_fname)}"

    ##
    ## Code for the image element, holding the page preview.
    ##

    # Note for future: if you pass a small test window you get the GUI controls AND
    # the non-image height.  Gives an upper bound, anyway, so you could size
    # the next test image better.  Detects GUI too big to fit in window.
    INITIAL_IMAGE = Image.new("L", INITIAL_IMAGE_SIZE, color=(222,)) # L = grey
    with io.BytesIO() as output:
        INITIAL_IMAGE.save(output, format="png")
        INITIAL_IMAGE = output.getvalue() # An in-memory PNG image.

    max_image_size = INITIAL_IMAGE_SIZE # This is temporary; size calculated and reset below.
    im_wid, im_ht = INITIAL_IMAGE_SIZE
    image_element = sg.Image(data=INITIAL_IMAGE, key="image_element",
                             pad=((0,5), (0,0)), expand_y=True) # make image element

    ##
    ## Code for handling page numbers.
    ##

    input_text_page_num = sg.Spin(values=spinner_values, initial_value=str(curr_page + 1),
                                  size=(5, 1), enable_events=True, key="PageNumber")
    text_page_num = sg.Text("Page:")

    def update_page_number(curr_page, prev_curr_page, num_pages, btn, value,
                           input_text_element):
        curr_page = max(curr_page, 0)
        curr_page = min(curr_page, num_pages-1)
        # Update page number field.
        input_text_element.Update(str(curr_page + 1))
        return curr_page

    ##
    ## Code for percentRetain options.
    ##

    args_dict["percentRetain"] = args.percentRetain
    if len(set(args.percentRetain4)) != 1: # Set initial value if all the same.
        args_dict["percentRetain"] = ["N/A"]
    text_percentRetain = sg.Text("percentRetain",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "percentRetain"))
    input_text_percentRetain = sg.InputText(args_dict["percentRetain"][0], pad=(0,0),
                                 size=(5, 1), do_not_clear=True, key="percentRetain")

    # Code for percentRetain4.
    args_dict["percentRetain4"] = args.percentRetain4
    text_percentRetain4 = sg.Text("percentRetain4",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "percentRetain4"))
    input_text_percentRetain4 = [sg.InputText(args_dict["percentRetain4"][i], size=(5, 1),
                                 do_not_clear=True, key=f"percentRetain4_{i}", pad=(1,0))
                                 for i in [0,1,2,3]]

    def update_percentRetain_values(values_dict):
        """Update both the percentRetain value and the percentRetain4 values."""
        update_paired_1_and_4_values(input_text_percentRetain,
                    input_text_percentRetain4, "percentRetain", "percentRetain4",
                    args_dict, values_dict)
        # Copy backing values to the actual args object.
        args.percentRetain = args_dict["percentRetain"]
        args.percentRetain4 = args_dict["percentRetain4"]

    update_funs.append(update_percentRetain_values)

    ##
    ## Code for absoluteOffset options.
    ##

    args_dict["absoluteOffset"] = args.absoluteOffset
    if len(set(args.absoluteOffset4)) != 1: # Set initial value if all the same.
        args_dict["absoluteOffset"] = ["N/A"]
    text_absoluteOffset = sg.Text("absoluteOffset",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "absoluteOffset"))
    input_text_absoluteOffset = sg.InputText(args_dict["absoluteOffset"][0], pad=(0,0),
                                 size=(5, 1), do_not_clear=True, key="absoluteOffset")

    # Code for absoluteOffset4.
    args_dict["absoluteOffset4"] = args.absoluteOffset4
    text_absoluteOffset4 = sg.Text("absoluteOffset4",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "absoluteOffset4"))
    input_text_absoluteOffset4 = [sg.InputText(args_dict["absoluteOffset4"][i], size=(5, 1),
                                 do_not_clear=True, key=f"absoluteOffset4_{i}", pad=(1,0))
                                 for i in [0,1,2,3]]

    def update_absoluteOffset_values(values_dict):
        """Update both the absoluteOffset value and the absoluteOffset4 values."""
        update_paired_1_and_4_values(input_text_absoluteOffset,
                    input_text_absoluteOffset4, "absoluteOffset", "absoluteOffset4",
                    args_dict, values_dict)
        # Copy backing values to the actual args object.
        args.absoluteOffset = args_dict["absoluteOffset"]
        args.absoluteOffset4 = args_dict["absoluteOffset4"]

    update_funs.append(update_absoluteOffset_values)

    ##
    ## Code for uniformOrderStat options.
    ##

    uniformOrderStat_spinner_values = tuple(range(0, num_pages))
    if args.uniformOrderStat:
        args_dict["uniformOrderStat"] = args.uniformOrderStat
    else:
        args_dict["uniformOrderStat"] = [0]

    if args.uniformOrderStat4:
        args_dict["uniformOrderStat4"] = args.uniformOrderStat4
        if len(set(args.uniformOrderStat4)) != 1: # Set initial value if all the same.
            args_dict["uniformOrderStat"] = [0]
        else:
            args_dict["uniformOrderStat"] = [args.uniformOrderStat4[0]]
    elif args.uniformOrderStat:
        args_dict["uniformOrderStat4"] = [args.uniformOrderStat[0]] * 4
    else:
        args_dict["uniformOrderStat4"] = [0] * 4

    dummy_spacing_spinner = sg.Text("", size=(7,1), pad=(0,0))

    text_uniformOrderStat = sg.Text("uniformOrderStat",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "uniformOrderStat"))
    input_text_uniformOrderStat = sg.Spin(values=uniformOrderStat_spinner_values,
                                 initial_value=args_dict["uniformOrderStat"][0], pad=(0,0),
                                 size=(5, 1), enable_events=True, key="uniformOrderStat")

    # Code for uniformOrderStat4.
    text_uniformOrderStat4 = sg.Text("uniformOrderStat4",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "uniformOrderStat4"))
    input_text_uniformOrderStat4 = [sg.Spin(values=uniformOrderStat_spinner_values,
                                    initial_value=args_dict["uniformOrderStat4"][i], size=(5, 1),
                                    enable_events=True, key=f"uniformOrderStat4_{i}", pad=(1,0))
                                    for i in [0,1,2,3]]

    def update_uniformOrderStat_values(values_dict):
        """Update both the uniformOrderStat value and the uniformOrderStat4 values."""
        update_paired_1_and_4_values(input_text_uniformOrderStat,
              input_text_uniformOrderStat4, "uniformOrderStat",
              "uniformOrderStat4", args_dict, values_dict,
              value_type=to_int_or_NA, value_type4=int, max_val=num_pages-1, min_val=0)
        # Copy backing values to the actual args object.
        args.uniformOrderStat = [] # Not needed with uniformOrderStat4 always set.
        if all(i == 0 for i in args_dict["uniformOrderStat4"]):
            args.uniformOrderStat4 = [] # Need to empty it, since it implies uniform option.
        else:
            args.uniformOrderStat4 = args_dict["uniformOrderStat4"]

    update_funs.append(update_uniformOrderStat_values)

    ##
    ## Code for uniform.
    ##

    checkbox_uniform = sg.Checkbox("uniform", pad=((0,10), None), key="uniform",
                                    tooltip=get_help_text_string_for_tooltip(cmd_parser,
                                        "uniform"),
                                    enable_events=True, default=args.uniform)

    def update_uniform(values_dict):
        """Update the uniform values."""
        update_checkbox(values_dict, checkbox_uniform, "uniform", args, "uniform")

    update_funs.append(update_uniform)

    ##
    ## Code for samePageSize.
    ##

    checkbox_samePageSize = sg.Checkbox("samePageSize", pad=((0,10), None),
                                         key="samePageSize", enable_events=True,
                                         tooltip=get_help_text_string_for_tooltip(
                                             cmd_parser, "samePageSize"),
                                         default=args.samePageSize)

    def update_samePageSize(values_dict):
        """Update the samePageSize values."""
        update_checkbox(values_dict, checkbox_samePageSize, "samePageSize", args,
                         "samePageSize")

    update_funs.append(update_samePageSize)

    ##
    ## Code for evenodd option.
    ##

    checkbox_evenodd = sg.Checkbox("evenodd", pad=((0,0), None),
                                    key="evenodd", enable_events=True,
                                    tooltip=get_help_text_string_for_tooltip(
                                        cmd_parser, "evenodd"),
                                    default=args.evenodd)

    def update_evenodd(values_dict):
        """Update the evenodd values."""
        update_checkbox(values_dict, checkbox_evenodd, "evenodd", args, "evenodd")

    update_funs.append(update_evenodd)

    ##
    ## Code for percentText.
    ##

    checkbox_percentText = sg.Checkbox("percentText", pad=((0,10), None), key="percentText",
                                    tooltip=get_help_text_string_for_tooltip(cmd_parser,
                                        "percentText"),
                                    enable_events=True, default=args.percentText)

    def update_percentText(values_dict):
        """Update the percentText values."""
        update_checkbox(values_dict, checkbox_percentText, "percentText", args, "percentText")

    update_funs.append(update_percentText)

    ##
    ## Code for cropSafe.
    ##

    checkbox_cropSafe = sg.Checkbox("cropSafe", pad=((0,10), None), key="cropSafe",
                                    tooltip=get_help_text_string_for_tooltip(cmd_parser,
                                        "cropSafe"),
                                    enable_events=True, default=args.cropSafe)

    def update_cropSafe(values_dict):
        """Update the cropSafe values."""
        update_checkbox(values_dict, checkbox_cropSafe, "cropSafe", args, "cropSafe")

    update_funs.append(update_cropSafe)


    ##
    ## Code for pages option.
    ##

    args_dict["pages"] = args.pages if args.pages else ""
    text_pages = sg.Text("pages", pad=((0,22), None),
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "pages"))
    input_text_pages = sg.InputText(args_dict["pages"],
                                 size=(7, 1), do_not_clear=True, key="pages")

    def update_pages_values(values_dict):
        """Update the pages value."""
        value = values_dict["pages"]
        try:
            if value: # Parse here only to test for errors.
                parse_page_range_specifiers(value, set(range(num_pages)))
        except ValueError:
            sg.PopupError(f"Bad page specifier '{value}'.")
            input_text_pages.Update("")
            args_dict["pages"] = ""
        else:
            args_dict["pages"] = values_dict["pages"]
        # Copy backing value to the actual args object.
        args.pages = args_dict["pages"] if args_dict["pages"] else None

    update_funs.append(update_pages_values)

    ##
    ## Code for restore.
    ##

    text_restore = sg.Text("restore", pad=(0,0),
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "restore"))

    combo_box_restore = sg.Combo(["True", "False"], readonly=True,
                                 default_value=str(args.restore), size=(5, 1),
                                 key="restore", enable_events=True)

    def update_restore(values_dict):
        """Update the restore values."""
        update_combo_box(values_dict, combo_box_restore, "restore", args, "restore",
                        fun_to_apply=str_to_bool)

    update_funs.append(update_restore)

    ##
    ## Code for setPageRatios option.
    ##

    args_dict["setPageRatios"] = args.setPageRatios if args.setPageRatios else ""
    text_setPageRatios = sg.Text("setPageRatios", pad=((0,25), None),
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "setPageRatios"))
    input_text_setPageRatios = sg.InputText(args_dict["setPageRatios"], pad=(0,0),
                                 size=(7, 1), do_not_clear=True, key="setPageRatios")

    def update_setPageRatios_values(values_dict):
        """Update the setPageRatios value."""
        value = values_dict["setPageRatios"]
        try:
            if value:
                parse_page_ratio_argument(value)
        except ValueError:
            sg.PopupError("Bad page ratio specifier.")
            input_text_setPageRatios.Update("")
            args_dict["setPageRatios"] = ""
        else:
            args_dict["setPageRatios"] = values_dict["setPageRatios"]
        # Copy backing value to the actual args object.
        if args_dict["setPageRatios"]:
            args.setPageRatios = parse_page_ratio_argument(args_dict["setPageRatios"])
        else:
            args.setPageRatios = None

    update_funs.append(update_setPageRatios_values)

    ##
    ## Code for pageRatioWeights options.
    ##

    args_dict["pageRatioWeights"] = args.pageRatioWeights
    text_pageRatioWeights = sg.Text("pageRatioWeights",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "pageRatioWeights"))
    input_text_pageRatioWeights = [sg.InputText(args_dict["pageRatioWeights"][i], size=(5, 1),
                                 do_not_clear=True, key=f"pageRatioWeights_{i}", pad=(1,0))
                                 for i in [0,1,2,3]]

    def update_pageRatioWeights_values(values_dict):
        """Update both the pageRatioWeights value and the pageRatioWeights values."""
        update_4_values(input_text_pageRatioWeights, "pageRatioWeights", args_dict, values_dict)

        # Copy backing values to the actual args object.
        args.pageRatioWeights = args_dict["pageRatioWeights"]

    update_funs.append(update_pageRatioWeights_values)

    ##
    ## Code for absolutePreCrop options.
    ##

    args_dict["absolutePreCrop"] = args.absolutePreCrop
    if len(set(args.absolutePreCrop4)) != 1: # Set initial value if all the same.
        args_dict["absolutePreCrop"] = ["N/A"]
    text_absolutePreCrop = sg.Text("absolutePreCrop",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "absolutePreCrop"))
    input_text_absolutePreCrop = sg.InputText(args_dict["absolutePreCrop"][0], pad=(0,0),
                                 size=(5, 1), do_not_clear=True, key="absolutePreCrop")

    # Code for absolutePreCrop4.
    args_dict["absolutePreCrop4"] = args.absolutePreCrop4
    text_absolutePreCrop4 = sg.Text("absolutePreCrop4",
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "absolutePreCrop4"))
    input_text_absolutePreCrop4 = [sg.InputText(args_dict["absolutePreCrop4"][i], size=(5, 1),
                                 do_not_clear=True, key=f"absolutePreCrop4_{i}", pad=(1,0))
                                 for i in [0,1,2,3]]

    def update_absolutePreCrop_values(values_dict):
        """Update both the absolutePreCrop value and the absolutePreCrop4 values."""
        update_paired_1_and_4_values(input_text_absolutePreCrop,
                    input_text_absolutePreCrop4, "absolutePreCrop", "absolutePreCrop4",
                    args_dict, values_dict)
        # Copy backing values to the actual args object.
        args.absolutePreCrop = args_dict["absolutePreCrop"]
        args.absolutePreCrop4 = args_dict["absolutePreCrop4"]

    update_funs.append(update_absolutePreCrop_values)

    ##
    ## Code for threshold option.
    ##

    args_dict["threshold"] = int(args.threshold[0]) if args.calcbb != "gb" else "----"
    text_threshold = sg.Text("threshold", pad=((0,0), None),
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "threshold"))
    input_num_threshold = sg.Spin(values=tuple(range(256)),
                                  initial_value=args_dict["threshold"],
                                  size=(3, 1), key="threshold")

    def update_threshold_values(values_dict):
        """Update the threshold value."""
        if args.calcbb == "gb":
            input_num_threshold.Update("----")
            return
        try:
            value = int(values_dict["threshold"])
            value = min(max(value, 0),  255)
            args_dict["threshold"] = value
        except ValueError:
            value = args_dict["threshold"]
        input_num_threshold.Update(value)
        # Copy backing value to the actual args object.
        args.threshold = [args_dict["threshold"]]

    update_funs.append(update_threshold_values)

    ##
    ## Code for numBlurs option.
    ##

    args_dict["numBlurs"] = int(args.numBlurs) if args.calcbb != "gb" else "--"
    text_numBlurs = sg.Text("numBlurs", pad=((0,0), None),
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "numBlurs"))
    input_num_numBlurs = sg.Spin(values=spinner_values,
                                 initial_value=args_dict["numBlurs"],
                                 size=(2, 1), key="numBlurs")

    def update_numBlurs_values(values_dict):
        """Update the numBlurs value."""
        if args.calcbb == "gb":
            input_num_numBlurs.Update("--")
            return
        try:
            value = int(values_dict["numBlurs"])
            value = max(value, 0)
            args_dict["numBlurs"] = value
        except ValueError:
            value = args_dict["numBlurs"]
        input_num_numBlurs.Update(value)
        # Copy backing value to the actual args object.
        args.numBlurs = args_dict["numBlurs"]

    update_funs.append(update_numBlurs_values)

    ##
    ## Code for numSmooths option.
    ##

    args_dict["numSmooths"] = int(args.numSmooths) if args.calcbb != "gb" else "--"
    text_numSmooths = sg.Text("numSmooths", pad=((0,0), None),
                      tooltip=get_help_text_string_for_tooltip(cmd_parser, "numSmooths"))
    input_num_numSmooths = sg.Spin(values=spinner_values,
                                   initial_value=args_dict["numSmooths"],
                                   size=(2, 1), key="numSmooths")

    def update_numSmooths_values(values_dict):
        """Update the numSmooths value."""
        if args.calcbb == "gb":
            input_num_numSmooths.Update("--")
            return
        try:
            value = int(values_dict["numSmooths"])
            value = max(value, 0)
            args_dict["numSmooths"] = value
        except ValueError:
            value = args_dict["numSmooths"]
        input_num_numSmooths.Update(value)
        # Copy backing value to the actual args object.
        args.numSmooths = args_dict["numSmooths"]

    update_funs.append(update_numSmooths_values)


    ##
    ## Code for wait indicator text box.
    ##

    wait_indicator_text = sg.Text("Calculating the crop,\nthis may take a while...",
                                  size=(None, None),
                                  auto_size_text=None,
                                  relief=sg.RELIEF_GROOVE,
                                  font=('Lucidia', 11),
                                  text_color=None,
                                  background_color="#DDDDDD",
                                  justification="center",
                                  # Workaround possible bug, initialize visible.  Below
                                  # it is updated to be invisible before the event loop.
                                  visible=True)

    ##
    ## Code for smallest delta display.
    ##

    smallest_delta_label_text = sg.Text("")
    # Note that the key is always returned/searched in the event loop if set, not the label.
    smallest_delta_left = sg.Button("", key="left_smallest_delta", pad=(2,2))
    smallest_delta_top = sg.Button("", key="top_smallest_delta", pad=(2,2))
    smallest_delta_bottom = sg.Button("", key="bottom_smallest_delta", pad=(2,2))
    smallest_delta_right = sg.Button("", key="right_smallest_delta", pad=(2,2))

    smallest_delta_values_display = [
                                     # Extraneous colums added because of this bug in tkinter:
                                     # https://github.com/PySimpleGUI/PySimpleGUI/issues/1154
                                     sg.Text("", size=(2,1)), # Spacing.
                                     sg.Column([[smallest_delta_left]], pad=(0,0)), # Extraneous col.
                                     sg.Column([[smallest_delta_top],
                                                [smallest_delta_bottom]], pad=(0,0)),
                                     sg.Column([[smallest_delta_right]], pad=(0,0)), # Extraneous col.
                                    ]

    def update_smallest_delta_values_display(delta_page_nums, disabled=False):
        smallest_delta_label_text.Update("Minimum cropping delta pages:")
        num_strings = [f"{i}" for i in delta_page_nums]
        max_len = max(len(i) for i in num_strings)
        num_strings = [" "*(max_len-len(i)) + i for i in num_strings] # Right-align.
        smallest_delta_left.Update(num_strings[0], visible=True, disabled=disabled)
        smallest_delta_top.Update(num_strings[3], visible=True, disabled=disabled)
        smallest_delta_bottom.Update(num_strings[1], visible=True, disabled=disabled)
        smallest_delta_right.Update(num_strings[2], visible=True, disabled=disabled)

    def set_delta_values_null():
        smallest_delta_label_text.Update("")
        smallest_delta_left.Update("", visible=False, disabled=True)
        smallest_delta_top.Update("", visible=False, disabled=True)
        smallest_delta_bottom.Update("", visible=False, disabled=True)
        smallest_delta_right.Update("", visible=False, disabled=True)

    def get_page_from_delta_page_nums(delta_page_nums, toggle, delta_index):
        if isinstance(delta_page_nums[delta_index], tuple):
            index = 0 if not toggle else 1
            page_num = delta_page_nums[delta_index][index] - 1
            toggle = not toggle
        else:
            page_num = delta_page_nums[delta_index] - 1
        return page_num, toggle

    ##
    ## Page image update and thread to redraw images on a configure/resize event.
    ##

    def get_max_image_size(window):
        """Return the largest size rectangle for the PDF image to fit into (after
        subtracting off the size of the non-image parts of the GUI).  This function
        should be called on a zoomed/fullscreen window."""
        max_image_size = (max(window.size[0]-non_image_size[0], FALLBACK_MAX_IMAGE_SIZE[0]),
                          max(window.size[1]-non_image_size[1], FALLBACK_MAX_IMAGE_SIZE[1]))
        return max_image_size

    def update_page_image(window, reset_cached=False, zoom=False, max_image_size=None,
                          update_image_element=True):
        """Calculate and return data for the image in the PDF preview.  If
        `max_image_size` is not passed in (the default) it will be calculated.
        If `update_image_element` is true (the default) then the GUI image is
        updated with the newly calculated image data."""
        if max_image_size is None:
            max_image_size = get_max_image_size(window)
        image_data, clip_pos, im_ht, im_wid = document_pages.get_display_page(curr_page,
                                                    max_image_size=max_image_size,
                                                    zoom=zoom, reset_cached=reset_cached)
        if update_image_element:
            image_element.Update(data=image_data)
        return image_data, clip_pos, im_ht, im_wid

    def resize_window(window, document_pages, max_image_size, non_image_size,
                      im_wid=None, im_ht=None):
        """Calculate and set the window size based on the `non_image_size`
        of the GUI controls and borders and the image's width and height."""
        if im_wid and im_ht:
            wid = im_wid
            ht = im_ht
        else:
            max_wid, max_ht = document_pages.get_max_width_and_height()
            scale_to_pixels = min(max_image_size[0]/max_wid, max_image_size[1]/max_ht)
            wid = math.ceil(scale_to_pixels * max_wid) # Note: these NEED to be made int, unlike
            ht = math.ceil(scale_to_pixels * max_ht)   # Postscript points that can be fractional.

        new_window_size = (non_image_size[0] + wid,
                           non_image_size[1] + ht)
        window.size = new_window_size

    RESIZE_DELAY_SECS = 0.5 # Time to delay while user resizes window.
    resize_thread_running = False # Flag to only run one update thread.
    request_thread_exit = False # Flag used to kill thread on exit.

    def resize_page_on_configure_event(delay_secs=RESIZE_DELAY_SECS,
                                       max_image_size=None):
        """This function is run as a thread to redraw preview pages on configure
        events once the size stabilizes.  Note that this routine sets the nonlocal
        variables `user_selected_max_image_size`, `old_window_size` (and the flag
        `resize_thread_running`).  Resize scaling is to make the image fit in
        the max window size, according to it's largest dimension (width or height)"""
        nonlocal resize_thread_running, old_window_size, user_selected_max_image_size
        resize_thread_running = True

        # Wait for user to finish resizing.
        time.sleep(delay_secs)
        while window.size != old_window_size:
            if request_thread_exit:
                return
            old_window_size = window.size
            time.sleep(delay_secs)

        if max_image_size is None:
            max_image_size = get_max_image_size(window)
        # Note that if user_selected_max_image_size is passed in it gets reset to itself.
        user_selected_max_image_size = max_image_size # Saved as a user preference.

        if request_thread_exit:
            return
        resize_window(window, document_pages, max_image_size, non_image_size)

        if request_thread_exit:
            return
        # TODO: Is this update_page_image really necessary?  Should it come before
        # or after resize of window?
        image_data, clip_pos, im_ht, im_wid = update_page_image(window,
                                                                reset_cached=True,
                                                                zoom=zoom)

        # Set the old window size and exit thread.
        old_window_size = window.size
        resize_thread_running = False

    ##
    ## Code for disabling options that are implied by others.
    ##

    backing_uniform_checkbox_value = [args.uniform]

    def update_disabled_states(values_dict):
        """Disable widgets that are implied by other selected options."""
        # Disable the uniform checkbox (this option implies uniform cropping).
        # TODO: This should check when disabled then return to previous value, but that
        # is currently not working so it just disables/enables in whatever state.
        if args.uniformOrderStat4 or values_dict["evenodd"]:
            backing_uniform_checkbox_value[0] = values_dict["uniform"]
            checkbox_uniform.Update(True, disabled=True) # Show that these options imply uniform.
        else:
            if checkbox_uniform.Disabled:
                checkbox_uniform.Update(backing_uniform_checkbox_value[0], disabled=False)

    update_funs.append(update_disabled_states)

    ##
    ## Setup and assign the window's layout.
    ##

    layout = [ # The overall window layout.
        [
            sg.Button("Prev"),
            sg.Button("Next"),
            text_page_num,
            input_text_page_num,
            sg.Text(f"({num_pages})      "), # Show max page count.
            sg.Button("Toggle Zoom"),
            sg.Text("(arrow keys navigate while zooming)"),
            #sg.Push(),
            #sg.Text("Quadruples are left, top, bottom, and right margins.\n"
            #                 "Mouse left over option names to show descriptions.",
            #                 expand_x=True,
            #                 relief=sg.RELIEF_GROOVE, justification="right", pad=((0,0), (0,0)))
            ],
        [
            image_element,
            sg.Push(),
            sg.Column([
                    # TODO: Consider this new layout, commented out, image to right
                    # and top controls moved to be with other controls.  Could move
                    # page controls and keep image to left, alternatively.
                    #[
                    # text_page_num,
                    # input_text_page_num,
                    # sg.Text(f"({num_pages}) "),
                    # sg.Button("Prev"),
                    # sg.Button("Next"),
                    # ],
                    #
                    #[sg.Text("Arrow keys move while zooming.", pad=(None, 0)),
                    # sg.Button("Toggle Zoom"),],
                    #[sg.Text("", size=(1,1))], # This is for vertical space.

                    [sg.Text("Quadruples are left, top, bottom, and right margins.\n"
                             "Mouse left over option names to show descriptions.",
                             relief=sg.RELIEF_GROOVE, pad=(None, (0,5)))], # Extra pad on bottom.

                    [checkbox_uniform, checkbox_samePageSize, checkbox_evenodd],

                    # percentRetain
                    [sg.Text("", size=input_text_percentRetain.Size,
                             pad=input_text_percentRetain4[0].Pad), # Empty text is space.
                        input_text_percentRetain, text_percentRetain, checkbox_percentText],

                    # percentRetain4
                    [input_text_percentRetain4[0],
                        sg.Column([[input_text_percentRetain4[3]],
                                   [input_text_percentRetain4[1]]], pad=(0,5)),
                        input_text_percentRetain4[2]] + [text_percentRetain4],

                    # absoluteOffset
                    [sg.Text("", size=input_text_absoluteOffset.Size,
                             pad=input_text_absoluteOffset4[0].Pad), # Empty text is space.
                        input_text_absoluteOffset, text_absoluteOffset, checkbox_cropSafe],

                    # absoluteOffset4
                    [input_text_absoluteOffset4[0],
                        sg.Column([[input_text_absoluteOffset4[3]],
                                   [input_text_absoluteOffset4[1]]], pad=(0,5)),
                        input_text_absoluteOffset4[2]] + [text_absoluteOffset4],

                    # uniformOrderStat
                    [dummy_spacing_spinner, input_text_uniformOrderStat, text_uniformOrderStat],

                    # uniformOrderStat4
                    [input_text_uniformOrderStat4[0],
                        sg.Column([[input_text_uniformOrderStat4[3]],
                                   [input_text_uniformOrderStat4[1]]], pad=(0,5)),
                        input_text_uniformOrderStat4[2]] + [text_uniformOrderStat4],

                    # setPageRatios
                    [sg.Text("", size=input_text_uniformOrderStat.Size,
                             pad=input_text_uniformOrderStat4[0].Pad), # Empty text is space.
                        input_text_setPageRatios, text_setPageRatios],

                    # pageRatioWeights
                    [input_text_pageRatioWeights[0],
                        sg.Column([[input_text_pageRatioWeights[3]],
                                   [input_text_pageRatioWeights[1]]], pad=(0,5)),
                        input_text_pageRatioWeights[2]] + [text_pageRatioWeights],

                    # absolutePreCrop
                    [sg.Text("", size=input_text_absolutePreCrop.Size,
                             pad=input_text_absolutePreCrop4[0].Pad), # Empty text is space.
                        input_text_absolutePreCrop, text_absolutePreCrop],

                    # absolutePreCrop4
                    [input_text_absolutePreCrop4[0],
                        sg.Column([[input_text_absolutePreCrop4[3]],
                                   [input_text_absolutePreCrop4[1]]], pad=(0,5)),
                        input_text_absolutePreCrop4[2]] + [text_absolutePreCrop4],

                    # threshold, numBlurs, numSmooths
                    [input_num_threshold, text_threshold, input_num_numBlurs,
                        text_numBlurs, input_num_numSmooths, text_numSmooths],

                    # pages
                    [input_text_pages, text_pages, combo_box_restore, text_restore],

                    # buttons
                    [sg.Button("Crop"), sg.Button("Original"), sg.Button("Exit"),],
                    #[sg.Text("", size=(1,1))], # This is for vertical space.
                    [smallest_delta_label_text],
                    smallest_delta_values_display,
                    [sg.Text("")], # This is for vertical space.
                    [sg.Text("", size=(5, 2)), wait_indicator_text],
                ], pad=(None,0), vertical_alignment="top", size=(None, None)), # End of column.
            #image_element,
            ],
        ]

    ##
    ## Get the full window size.
    ##

    scaling = 1.0 # Note setting to None vs. 1.0 causes sizing issue on smaller-screen laptop.
    x_res, y_res, x_pos, y_pos = parse_geometry_string(args)

    left_pixels = 20
    top_pixels = 0
    if x_pos is None or y_pos is None:
        x_pos = left_pixels
        y_pos = 0
    else:
        left_pixels = x_pos
        top_pixels = y_pos

    if x_res and y_res:
        full_window_width, full_window_height = x_res, y_res
    else:
        full_window_width, full_window_height = get_window_size(scaling)

    ##
    ## Setup the fonts.
    ##

    if args.guiFontSize:
        gui_font_size = args.guiFontSize
    elif ex.system_os == "Windows":
        gui_font_size = 12
    else:
        gui_font_size = 11

    try:
        gui_font_size = int(gui_font_size)
    except TypeError:
        print("Error in pdfCropMargins: Font size specification could not be made"
              " an integer.", file=sys.stdout)
        ex.cleanup_and_exit(1)

    gui_font_name = "Helvetica"
    font = (gui_font_name, gui_font_size)

    if ex.system_os == "Windows":
        tooltip_font_size = gui_font_size + 1
    else:
        tooltip_font_size = gui_font_size - 1

    tooltip_font_name = "Ariel"
    sg.set_options(tooltip_font=(f"{tooltip_font_name} {tooltip_font_size}"))

    ##
    ## Create the main window.
    ##

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Your title is not a string.")
        window = sg.Window(title=window_title, layout=layout, return_keyboard_events=True,
                           location=(x_pos, y_pos), resizable=True, no_titlebar=False,
                           scaling=scaling,
                           #use_ttk_buttons=True, ttk_theme=sg.THEME_DEFAULT,
                           use_default_focus=False, font=font, alpha_channel=0, finalize=True)

    window.bind('<Configure>', "Configure") # Detect tkinter window-resize events.

    ##
    ## Find the usable window size.
    ##

    max_image_size, non_image_size = get_usable_image_size(args, window, full_window_width,
                                                           full_window_height,
                                                           im_wid, im_ht, left_pixels,
                                                           top_pixels)

    user_selected_max_image_size = max_image_size # Saved as a user preference.

    # Update visibility of invisible elements after getting full size.
    set_delta_values_null() # Set the delta values buttons to visible=False and null text.
    wait_indicator_text.Update(visible=False)

    # Update the page image (currently set to a small size above) to fit resized window.
    resize_window(window, document_pages, max_image_size, non_image_size)
    image_data, clip_pos, im_ht, im_wid = update_page_image(window,
                                                            reset_cached=True,
                                                            zoom=False,
                                                            max_image_size=max_image_size)
    old_window_size = window.size

    window.alpha_channel = 1 # Make the window visible.

    ##
    ## Run the main event loop.
    ##

    zoom = False
    did_crop = False
    bounding_box_list = None

    last_pre_crop = None
    last_threshold = None
    last_numSmooths = None
    last_numBlurs = None

    old_window_size = window.size

    while True:
        page_change_event = False
        update_page_image_event = False
        resize_window_event = False

        prev_curr_page = curr_page
        event, values_dict = window.Read()

        if event is None and (values_dict is None or values_dict["PageNumber"] is None):
            break

        if event == sg.WIN_CLOSED or Events.is_exit(event):
            if resize_thread_running:
                request_thread_exit = True
            break

        if Events.is_enter(event):
            # This is for when a page number is manually entered in the window.
            call_all_update_funs(update_funs, values_dict)
            try:
                curr_page = int(values_dict["PageNumber"]) - 1  # check if valid
            except: # TODO: Use explicit exceptions,
                curr_page = prev_curr_page
            page_change_event = True

        if Events.is_page_num_change(event):
            call_all_update_funs(update_funs, values_dict)
            try:
                curr_page = int(values_dict["PageNumber"]) - 1  # check if valid
            except: # TODO: use explicit exceptions.
                curr_page = prev_curr_page
            page_change_event = True

        elif Events.is_next(event):
            curr_page += 1
            page_change_event = True

        elif Events.is_prev(event):
            curr_page -= 1
            page_change_event = True

        elif Events.is_up(event) and zoom:
            zoom = (clip_pos, 0, -1)
            update_page_image_event = True

        elif Events.is_down(event) and zoom:
            zoom = (clip_pos, 0, 1)
            update_page_image_event = True

        elif Events.is_home(event):
            curr_page = 0
            page_change_event = True

        elif Events.is_end(event):
            curr_page = num_pages - 1
            page_change_event = True

        elif Events.is_left(event) and zoom:
            zoom = (clip_pos, -1, 0)
            update_page_image_event = True

        elif Events.is_right(event) and zoom:
            zoom = (clip_pos, 1, 0)
            update_page_image_event = True

        elif Events.is_zoom(event): # Toggle.
            if not zoom:
                zoom = (clip_pos, 0, 0)
            else:
                zoom = False
            update_page_image_event = True

        elif Events.is_crop(event):
            call_all_update_funs(update_funs, values_dict)
            document_pages.close_document()

            # Display the wait message as a popup (unused alternative).
            #nonblock_popup = sg.PopupNoWait(
            #        "Finding the bounding boxes,\nthis may take some time...",
            #        keep_on_top=True,
            #        title="pdfCropMargins version {}.".format(__version__),
            #        button_type=5,
            #        button_color=None,
            #        background_color=None,
            #        text_color=None,
            #        auto_close=True,
            #        auto_close_duration=2,
            #        non_blocking=True,
            #        icon=None,
            #        line_width=None,
            #        font=None,
            #        no_titlebar=True,
            #        grab_anywhere=True,
            #        location=(100,100))
            wait_indicator_text.Update(visible=True)
            window.Refresh()

            # If the pre-crop values changed then bounding boxes must be redone.
            all_pre_crop = args.absolutePreCrop + args.absolutePreCrop4
            if last_pre_crop != all_pre_crop:
                bounding_box_list = None # Kill saved bounding boxes.
                last_pre_crop = all_pre_crop
            # New thresholding params also require recalculation of bounding boxes.
            if last_threshold != args.threshold[0]:
                bounding_box_list = None
                last_threshold = args.threshold[0]
            if last_numBlurs != args.numBlurs:
                bounding_box_list = None
                last_numBlurs = args.numBlurs
            if last_numSmooths != args.numSmooths:
                bounding_box_list = None
                last_numSmooths = args.numSmooths

            # Do the crop, saving the bounding box list.
            bounding_box_list, delta_page_nums = process_pdf_file(input_doc_fname,
                                                                  fixed_input_doc_fname,
                                                                  output_doc_fname,
                                                                  bounding_box_list)

            update_smallest_delta_values_display(delta_page_nums, disabled=args.restore)

            left_smallest_toggle = False
            top_smallest_toggle = False
            bottom_smallest_toggle = False
            right_smallest_toggle = False

            if args.restore:
                combo_box_restore.Update("False")

            # Change the view to the new cropped file.
            num_pages = document_pages.open_document(output_doc_fname)
            did_crop = True
            wait_indicator_text.Update(visible=False)

            update_page_image_event = True
            resize_window_event = True

            if parsed_args.verbose:
                print("\nWaiting for the GUI...")

        elif Events.is_original(event):
            call_all_update_funs(update_funs, values_dict)
            document_pages.close_document()
            num_pages = document_pages.open_document(fixed_input_doc_fname)
            did_crop = False
            set_delta_values_null()
            update_page_image_event = True
            resize_window_event = True

        elif Events.is_left_smallest_delta(event):
            curr_page, left_smallest_toggle = get_page_from_delta_page_nums(
                                                              delta_page_nums,
                                                              left_smallest_toggle, 0)
            page_change_event = True

        elif Events.is_top_smallest_delta(event):
            curr_page, top_smallest_toggle = get_page_from_delta_page_nums(
                                                              delta_page_nums,
                                                              top_smallest_toggle, 3)
            page_change_event = True

        elif Events.is_bottom_smallest_delta(event):
            curr_page, bottom_smallest_toggle = get_page_from_delta_page_nums(
                                                              delta_page_nums,
                                                              bottom_smallest_toggle, 1)
            page_change_event = True

        elif Events.is_right_smallest_delta(event):
            curr_page, right_smallest_toggle = get_page_from_delta_page_nums(
                                                              delta_page_nums,
                                                              right_smallest_toggle, 2)
            page_change_event = True

        elif Events.is_paired_single_and_quadruple_change(event):
            call_all_update_funs(update_funs, values_dict)

        elif Events.is_evenodd(event):
            call_all_update_funs(update_funs, values_dict)

        elif Events.is_general_checkbox_click(event):
            # This was added to try to make things more responsive on Windows, where multiple
            # checkbox clicks become unresponsive until something else is clicked or return
            # is entered in a box.  Doesn't help much.
            call_all_update_funs(update_funs, values_dict)

        elif Events.is_configure(event): # Capture tkinter window resizes.
            if window.size != old_window_size and not resize_thread_running:
                # Note possible threading bug, calling pysimplegui from a thread:
                # https://github.com/PySimpleGUI/PySimpleGUI/issues/4051
                request_thread_exit = False
                proc = threading.Thread(target=resize_page_on_configure_event)
                proc.daemon = True
                proc.start()

        if page_change_event:
            curr_page = update_page_number(curr_page, prev_curr_page, num_pages, event,
                                      values_dict["PageNumber"], input_text_page_num)

        # Resize the main GUI window if such an event was triggered.
        if resize_window_event:
            resize_page_on_configure_event(delay_secs=0,
                                           max_image_size=user_selected_max_image_size)

        # Get the current page and display it.
        if update_page_image_event or page_change_event:
            reset_cached = Events.is_crop(event)
            image_data, clip_pos, im_ht, im_wid = update_page_image(window,
                                                                    reset_cached=reset_cached,
                                                                    zoom=zoom)

    window.Close()
    document_pages.close_document() # Be sure document is closed (bug with -mo without this).
    return did_crop, bounding_box_list, delta_page_nums

#
# General helper functions.
#

wrapper = textwrap.TextWrapper(initial_indent="", subsequent_indent="", width=45,
                               break_on_hyphens=False)

def get_help_text_string_for_tooltip(cmd_parser, option_string):
    """Extract the help message for an option from an argparse command parser.
    This gets the argparse help string to use as a tooltip."""
    for a in cmd_parser._actions:
        if "--" + option_string in a.option_strings:
            help_text = a.help
            option_list = a.option_strings
            break
    else:
        return None
    help_text = textwrap.dedent(help_text)
    formatted_para = wrapper.fill(help_text)
    combined_para = " ".join(option_list) + "\n\n" + formatted_para
    combined_para = combined_para.replace("^^n", "\n")
    return combined_para

def get_filename():
    """Get the filename of the PDF file via GUI if one was not passed in."""
    # TODO: This isn't used now, but the code works to pop up a file chooser.
    # Incorporate it to interactively find the file to crop if none passed in.
    fname = sg.PopupGetFile("Select file and filetype to open:",
                            title="pdfCropMargins: Document Browser",
                            file_types=[ # Only PDF files.
                                          ("PDF Files", "*.pdf"),
                                       ],
                            )
    return fname # Might be None.

