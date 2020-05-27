""" Multi-Patient Planning Study
    
    Automatic generation of a curative Head and Neck Plan.  
    -Load the patient and case from a user-selected csv file
    -Loads planning structures
    -Loads Beams (or templates)
    -Loads clinical goals
    -Loads plan optimization templates
    -Runs an optimization script
    -Saves the plan for future comparisons
    Examination and Case must exist up front

    This program is free software: you can redistribute it and/or modify it under
    the terms of the GNU General Public License as published by the Free Software
    Foundation, either version 3 of the License, or (at your option) any later
    version.
    
    This program is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
    FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License along with
    this program. If not, see <http://www.gnu.org/licenses/>.
    """

__author__ = 'Adam Bayliss'
__contact__ = 'rabayliss@wisc.edu'
__date__ = '2018-Mar-28'
__version__ = '1.0.1'
__status__ = 'Production'
__deprecated__ = False
__reviewer__ = 'Someone else'
__reviewed__ = 'YYYY-MM-DD'
__raystation__ = '6.0.0'
__maintainer__ = 'One maintainer'
__email__ = 'rabayliss@wisc.edu'
__license__ = 'GPLv3'
__copyright__ = 'Copyright (C) 2018, University of Wisconsin Board of Regents'
__credits__ = ['']

import sys
import os
import csv
import logging
import xml
import pandas as pd
import numpy as np
import random
import logging

import connect
import GeneralOperations
import StructureOperations
import BeamOperations
import UserInterface

def output_status(path, input_filename, patient_id, case_name, plan_name, beamset_name,
                  patient_load, planning_structs, beams_load, clinical_goals_load,
                  plan_optimization_strategy_load, optimization_complete, script_status):
    """
    Write out the status of the optimization for a given patient

    Arguments:
        path {[string]} -- path for output file
        input_filename {[string]} -- name of file for input (.csv)
        patient_id {[string]} -- Patient ID under auto-planning
        case {[string]} -- RS case name
        plan_name {[string]} -- RS Plan name
        beamset_name {[string]} -- RS beamset name
        patient_load {[bool]} -- Did the patient load successfully
        planning_structs {[bool]} -- Were planning structures loaded
        beams_load {[bool]} --  Did Beams load
        clinical_goals_load {[bool]} -- Clinical Goals and Plan Objectives loaded
        plan_optimization_strategy_load {[bool]} -- An optimization strategy was loaded
        optimization_complete {[bool]} -- Optimization ended successfully
        script_status {[string]} -- Error messages if applicable, success otherwise
    """

    # Create the output file
    path = os.path.dirname(input_filename)
    output_filename = os.path.join(path, input_filename.replace(".csv","_output.txt"))
    # Determine if a filename exists and is empty
    if os.path.exists(output_filename) and os.stat(output_filename).st_size != 0:
        output_file = open(output_filename, "a+")
        logging.debug('Output directed to {}'.format(output_filename))
    else:
        # The file does not currently exist or is empty
        output_file = open(output_filename, "w+")
        # Write the header
        output_message = \
                   "PatientID" + ",\t" \
                   "Case" + ",\t" \
                   "Plan" + ",\t" \
                   "Beamset" + ",\t" \
                   "Patient Loaded" + ",\t" \
                   "Planning Structs Loaded" + ",\t" \
                   "Beams Loaded" + ",\t" \
                   "Clinical Goals Loaded" + ",\t" \
                   "Optimization Strategy Loaded" + ",\t" \
                   "Optimization Completed" + ",\t" \
                   "Plan Complete" + "\n"
        output_file.write(output_message)
        logging.debug('Header written to {}'.format(output_filename))
    #
    output_file = open(output_filename, "a+")
    if script_status is None:
        script_status = 'success'
    output_message = \
          patient_id + ",\t" \
        + case_name + ",\t" \
        + plan_name + ",\t" \
        + beamset_name + ",\t" \
        + str(patient_load) + ",\t" \
        + str(planning_structs) + ",\t" \
        + str(beams_load) + ",\t" \
        + str(clinical_goals_load) + ",\t" \
        + str(plan_optimization_strategy_load) + ",\t" \
        + str(optimization_complete) + ",\t" \
        + str(script_status) + "\n" 
    output_file.write(output_message)
    output_file.close()


def load_patient_data(patient_id, first_name, last_name, case_name, exam_name, plan_name):
    """ Query's database for plan, case, and exam. Returns them as a dict. Saves patient if a 
        new plan is created.

    Arguments:
        patient_id {string} -- Patient's ID in database
        first_name {string} -- Patient first name
        last_name {string} -- Patient Last Name
        case_name {string} -- RS case name
        exam_name {string} -- RS Exam Name
        plan_name {string} -- RS plan

    Returns:
        dict -- {'Case': RS Case Object, 'Exam' RS Exam object,
                 'Plan': RS Plan Object - either existing or new}
    """
    # Initialize return variable
    patient_data = {'Error': [],
                    'Case': None,
                    'Patient': None,
                    'Exam': None,
                    'Plan': None}
    db = connect.get_current("PatientDB")
    # Find the patient in the database
    patient_info = db.QueryPatientInfo(
        Filter={
            'FirstName': '^{0}$'.format(first_name),
            'LastName': '^{0}$'.format(last_name),
            'PatientID': '^{0}$'.format(patient_id)
        }
    )
    if len(patient_info) != 1:
        patient_data['Error'] = ['Patient {} {}, ID: {} not found'.format(
            first_name, last_name, patient_id
        )]
        return patient_data
    else:
        # Set the appropriate parameters for this patient
        patient = db.LoadPatient(PatientInfo=patient_info[0])
        patient_data['Patient'] = patient
    # Load case
    # See if the case exists
    try:
        case = patient.Cases[case_name]
        patient_data['Case'] = case
    except SystemError:
        patient_data['Error'].append('Case {} not found'.format(case_name))
        return patient_data
    # 
    # Load examination
    try:
        info = db.QueryExaminationInfo(PatientInfo = patient_info[0],
                                        Filter = {'Name': exam_name})
        if info[0]['Name'] == exam_name:
            ## Raystation sets the value of an anonymized CT ID to -sys.maxint -1
            ##   causing the ID key to be non unique.
            ## info_name = {'Name': exam_name}
            ## exam = case.LoadExamination( ExaminationInfo = info_name)
            exam = case.Examinations[exam_name]
            patient_data['Exam'] = exam
    except IndexError:
        patient_data['Error'].append('Exam {} not found'.format(exam_name)) 
        return patient_data
    #
    # Load the plan indicated
    # If the plan is found, cool. just make it current
    try:
        info = case.QueryPlanInfo(Filter = {'Name': plan_name})
        if info[0]['Name'] == plan_name:
            patient_data['Plan'] = case.TreatmentPlans[plan_name]
    except IndexError:
        case.AddNewPlan(
            PlanName=plan_name,
            PlannedBy='H.A.L.',
            Comment='Diagnosis',
            ExaminationName=exam.Name,
            AllowDuplicateNames=False
        )
        patient_data['Plan'] = case.TreatmentPlans[plan_name]
        # Plan creation modification requires a patient save
        patient.Save()
    try:
        test_plan = case.TreatmentPlans[plan_name]
    except IndexError:
        patient_data['Error'].append('Plan {} not found'.format(plan_name))
        return patient_data

    return patient_data

def merge_dict(row):
        """
        A variable number of input targets may be used in the csv file
        this function returns a dictionary that can be used to merge target columns
        Arguments:
           row {dataframe row} -- input row from the plan_data dataframe
        Returns:
           [dict] -- dictionary of the form {'PTV1_6000': 6000, ...}
        """
        target_column_exists = True
        target_columns = 0 
        target_dict = {}
        while target_column_exists:
            try:
                target_name = 'Target' + str(target_columns+1).zfill(2)
                target_dose = 'TargetDose' + str(target_columns+1).zfill(2)
                if not np.isnan(row[target_dose]):
                    target_dict[row[target_name]] = row[target_dose]
                target_columns += 1
            except KeyError:
                target_column_exists = False
        return target_dict

# def create_beamset(beamset_name, df_input, suffix=):
#    """Create a beamset from """
def main():
    # Load the current RS database
    ## db = connect.get_current("PatientDB")
    # Prompt the user to open a file
    browser = UserInterface.CommonDialog()
    file_csv = browser.open_file('Select a plan list file', 'CSV Files (*.csv)|*.csv')
    if file_csv != '':
        plan_data = pd.read_csv(file_csv)
        # Merge the target rows into a dictionary containing {[Target Name]:Dose}
        plan_data['Targets'] = plan_data.apply(lambda row: merge_dict(row), axis=1)
    ## Create the output file
    path = os.path.dirname(file_csv)
    ## output_filename = os.path.join(path, file_csv.replace(".csv","_output.txt"))
    # Cycle through the input file
    for index, row in plan_data.iterrows():
        beamset_name = row.BeamsetName
        plan_name = row.PlanName
        patient_id = row.PatientID
        case_name = row.Case
        patient_load = False
        planning_structs= False
        beams_load = False
        clinical_goals_load = False
        plan_optimization_strategy_load = False
        optimization_complete = False
        #
        # Read the csv into a pandas dataframe
        patient_data = load_patient_data(
                                         patient_id=patient_id,
                                         first_name=row.FirstName,
                                         last_name=row.LastName,
                                         case_name=case_name,
                                         exam_name=row.ExaminationName,
                                         plan_name=plan_name,
                                         )
        # Check loading status
        if patient_data['Error']:
            # Go to the next entry
            output_status(
                      path=path,
                      input_filename=file_csv,
                      patient_id=patient_id,
                      case_name=case_name,
                      plan_name=plan_name,
                      beamset_name=beamset_name,
                      patient_load=patient_load,
                      planning_structs=planning_structs,
                      beams_load=beams_load,
                      clinical_goals_load=clinical_goals_load,
                      plan_optimization_strategy_load=plan_optimization_strategy_load,
                      optimization_complete=optimization_complete,
                      script_status=patient_data['Error']
            )
            continue
        else:
            patient = patient_data['Patient']
            exam = patient_data['Exam']
            case = patient_data['Case']
            plan = patient_data['Plan']
            case.SetCurrent()
            connect.get_current('Case')
            plan.SetCurrent()
            connect.get_current('Plan')
            patient_load = True

        # If this beamset is found, then append 1-99 to the name and keep going
        beamset_exists = True
        while beamset_exists:
            info = plan.QueryBeamSetInfo(Filter={'Name':'^{0}'.format(beamset_name)})
            try:
                if info[0]['Name'] == beamset_name:
                    beamset_name = (beamset_name[:14]
                                    + str(random.randint(1,99)).zfill(2)) \
                                    if len(beamset_name) > 14 \
                                    else beamset_name + str(random.randint(1,99)).zfill(2)
            except IndexError:
                beamset_exists = False
        # Resolve the path to the beamset file
        path_protocols = os.path.join(os.path.dirname(__file__),
                                  row.BeamsetPath)
        # Go grab the beamset called protocol_beamset
        # This step is likely not necessary, just know exact beamset name from protocol
        beamset_etree = BeamOperations.Beams.select_element(
            set_level='beamset',
            set_type=None,
            set_elements='beam',
            filename=row.BeamsetFile,
            set_level_name=row.ProtocolBeamset,
            dialog=False,
            folder=path_protocols,
            verbose_logging=False)[0]

        beamset_defs = BeamOperations.BeamSet()
        beamset_defs.rx_target = row.Target01
        beamset_defs.number_of_fractions = row.NumberFractions
        beamset_defs.total_dose = row.TargetDose01
        beamset_defs.machine = row.Machine
        beamset_defs.iso_target = row.Isotarget
        beamset_defs.name = beamset_name
        beamset_defs.DicomName = beamset_name
        beamset_defs.modality = 'Photons'
        # Beamset elements derived from the protocol
        beamset_defs.technique = beamset_etree.find('technique').text
        beamset_defs.protocol_name = beamset_etree.find('name').text

        order_name = None

        rs_beam_set = BeamOperations.create_beamset(patient=patient,
                                                    case=case,
                                                    exam=exam,
                                                    plan=plan,
                                                    dialog=False,
                                                    BeamSet=beamset_defs,
                                                    create_setup_beams=False)
        # ok, now make the beamset current
        patient.Save()
        rs_beam_set.SetCurrent()
        connect.get_current('BeamSet')
        beams = BeamOperations.load_beams_xml(filename=row.BeamsetFile,
                                              beamset_name=row.ProtocolBeamset,
                                              path=path_protocols)

        # Place isocenter
        try:
            beamset_defs.iso = BeamOperations.find_isocenter_parameters(
                case=case,
                exam=exam,
                beamset=rs_beam_set,
                iso_target=beamset_defs.iso_target,
                lateral_zero=True)
        except Exception:
            logging.warning('Aborting, could not locate center of {}'.format(beamset_defs.iso_target))
            sys.exit('Failed to place isocenter')
        # TODO: Need to parse tomo beams versus vmat
        if beamset_defs.technique == 'TomoHelical':
            if len(beams) > 1:
                logging.warning('Invalid tomo beamset in {}, more than one Tomo beam found.'.format(beamset_defs.name))
            else:
                beam = beams[0]
            BeamOperations.place_tomo_beam_in_beamset(plan=plan, iso=beamset_defs.iso,
                                                      beamset=rs_beam_set, beam=beam)
            # Beams loaded successfully
            beams_load = True
        elif beamset_defs.technique == 'VMAT':
            BeamOperations.place_beams_in_beamset(iso=beamset_defs.iso, beamset=rs_beam_set,
                                                  beams=beams)
            # Beams loaded successfully
            beams_load = True
        else:
            logging.debug('Unsupported beamset technique {}'.format(beamset_defs.technique))
        if not beams_load:
            output_status(
                          path=path,
                          input_filename=file_csv,
                          patient_id=patient_id,
                          case_name=case_name,
                          plan_name=plan_name,
                          beamset_name=beamset_name,
                          patient_load=patient_load,
                          planning_structs=planning_structs,
                          beams_load=beams_load,
                          clinical_goals_load=clinical_goals_load,
                          plan_optimization_strategy_load=plan_optimization_strategy_load,
                          optimization_complete=optimization_complete,
                          script_status= None
                )
            continue

        patient.Save()
        rs_beam_set.SetCurrent()
        if row.PlanningStructureWorkflow is not None:
            # path_planning_structure_protocol = os.path.join(os.path.dirname(__file__),
            #                       row.PlanningStructurePath)
            # Go get a dataframe for planning structures
            # Planning preferences loaded into tree
            planning_preferences_tree = xml.etree.ElementTree.parse(
                                            os.path.join(
                                                         os.path.dirname(__file__),
                                                         row.PlanningStructurePath,
                                                         row.PlanningStructureFile
                                                         )
                                            )
            # Planning preferences loaded into dict
            planning_preferences_dict = StructureOperations \
                                        .iter_planning_structure_etree(planning_preferences_tree)
            # Planning preferences loaded dataframe
            df_planning_preferences = pd.DataFrame(planning_preferences_dict['planning_structure_config'])
            # Select the dataframe row that matches the workflow name
            df_workflow = df_planning_preferences[df_planning_preferences.name == row.PlanningStructureWorkflow]
            # If we matched, then lets start setting up planning structures
            if df_workflow.empty:
                planning_structs = False
            else:
                planning_prefs = StructureOperations.planning_structure_preferences()
                planning_prefs.number_of_targets = row.NumberTargets
                planning_prefs.first_target_number = df_workflow.first_target_number.values[0]
                uniform_structures = df_workflow.uniform_structures.values[0]
                underdose_structures = df_workflow.underdose_structures.values[0]
                inner_air_name = df_workflow.inner_air_name.values[0]
                
                if uniform_structures:
                    planning_prefs.use_uniform_dose = True
                    dialog4_response = {'structures': df_workflow.uniform_structures.values[0],
                                        'standoff': df_workflow.uniform_standoff.values[0]}
                else:
                    planning_prefs.use_uniform_dose = False
                    dialog4_response = {'structures': [], 'standoff': None}

                if underdose_structures:
                    planning_prefs.use_under_dose = True
                    dialog3_response = {'structures': df_workflow.underdose_structures.values[0],
                                        'standoff': df_workflow.underdose_standoff.values[0]}
                else:
                    planning_prefs.use_under_dose = False
                    dialog3_response = {'structures': [], 'standoff': None}

                if inner_air_name:
                    planning_prefs.use_inner_air = True
                else:
                    planning_prefs.use_inner_air = False
                dialog1_response = {
                        'number_of_targets': planning_prefs.number_of_targets,
                        'generate_underdose': planning_prefs.use_under_dose,
                        'generate_uniformdose': planning_prefs.use_uniform_dose,
                        'generate_inner_air': planning_prefs.use_inner_air}
                dialog2_response = row.Targets
                ## dialog1_response = {'number_of_targets': 2,
                ##                     'generate_underdose': False,
                ##                     'generate_uniformdose': True,
                ##                     'generate_inner_air': False}
                ## targets_dose = {target_1: target_1_dose, target_2: target_2_dose, target_3: target_3_dose}
                ## dialog2_response = targets_dose
                ## dialog1_response = None
                ## dialog2_response = None
                # Underdose dialog, dictionary or none
                    
                ## dialog4_response = {'structures': ['Bone_Mandible', 'Larynx', 'Esophagus'],
                ##                 'standoff': 0.4}
                # TODO Add capabilites for handing a name and expansion for superficial targets,
                #       Make OTV's optional, add standoffs, 
                #       Add capabilities of specifinyg a ring HD/LD/targets thickness- with differential expansion,
                #           standoff etc...
                # Skin-superficial
                dialog5_response = {}
                if df_workflow.superficial_target_name.values[0]:
                    dialog5_response['target_skin'] = True
                else:
                    dialog5_response['target_skin'] = False
                # HD Ring
                if df_workflow.ring_hd_name.values[0]:
                    generate_ring_hd = True
                    dialog5_response['ring_hd'] = generate_ring_hd
                    dialog5_response['thick_hd_ring'] = df_workflow.ring_hd_ExpA.values[0][0]
                    dialog5_response['ring_standoff'] = df_workflow.ring_hd_standoff.values[0]
                else:
                    generate_ring_hd = False
                    dialog5_response['ring_hd'] = generate_ring_hd
                    dialog5_response['thick_hd_ring'] = None
                    dialog5_response['ring_standoff'] = None
                # LD Ring
                if df_workflow.ring_ld_name.values[0]:
                    generate_ring_ld = True
                    dialog5_response['ring_ld'] = generate_ring_ld
                    dialog5_response['thick_ld_ring'] = df_workflow.ring_ld_ExpA.values[0][0]
                    dialog5_response['ring_standoff'] = df_workflow.ring_hd_standoff.values[0]
                else:
                    generate_ring_ld = False
                    dialog5_response['ring_ld'] = generate_ring_ld
                    dialog5_response['thick_ld_ring'] = None
                # Target rings
                if df_workflow.ring_ts_name.values[0]:
                    dialog5_response['target_rings'] = True
                else:
                    dialog5_response['target_rings'] = False
                # OTV's
                if df_workflow.otv_name.values[0]:
                    dialog5_response['otv_standoff'] = df_workflow.otv_standoff.values[0]
                    generate_otvs = True
                else:
                    dialog5_response['otv_standoff'] = None
                    generate_otvs = False
                # Skin evals
                if df_workflow.skin_name.values[0]:
                    generate_skin = True
                    skin_contraction = df_workflow.skin_ExpA.values[0][0]
                else:
                    generate_skin = False
                    skin_contraction = None
                StructureOperations.planning_structures(
                    generate_ptvs=True,
                    generate_ptv_evals=True,
                    generate_otvs=generate_otvs,
                    generate_skin=generate_skin,
                    generate_inner_air=planning_prefs.use_inner_air,
                    generate_field_of_view=True,
                    generate_ring_hd=generate_ring_hd,
                    generate_ring_ld=generate_ring_ld,
                    generate_normal_2cm=True,
                    generate_combined_ptv=True,
                    skin_contraction=skin_contraction,
                    run_status=False,
                    planning_structure_selections=planning_prefs,
                    dialog2_response=dialog2_response,
                    dialog3_response=dialog3_response,
                    dialog4_response=dialog4_response,
                    dialog5_response=dialog5_response
                )
                ## dialog5_response = {'target_skin': False,
                ##                 'ring_hd': True,
                ##                 'target_rings': True,
                ##                 'thick_hd_ring': 2,
                ##                 'thick_ld_ring': 5,
                ##                 'ring_standoff': 0.2,
                ##                 'otv_standoff': 0.4}
                ## StructureOperations.planning_structures(
                ##    generate_ptvs=True,
                ##    generate_ptv_evals=True,
                ##    generate_otvs=True,
                ##    generate_skin=True,
                ##    generate_inner_air=True,
                ##    generate_field_of_view=True,
                ##    generate_ring_hd=True,
                ##    generate_ring_ld=True,
                ##    generate_normal_2cm=True,
                ##    generate_combined_ptv=True,
                ##    skin_contraction=0.3,
                ##    run_status=False,
                ##    planning_structure_selections=planning_prefs,
                ##    dialog2_response=dialog2_response,
                ##    dialog3_response=dialog3_response,
                ##    dialog4_response=dialog4_response,
                ##    dialog5_response=dialog5_response
                ##)
        ## # Go grab the beamset called protocol_beamset
        ## # This step is likely not necessary, just know exact beamset name from protocol
        ## planning_struct_etree = BeamOperations.Beams.select_element(
        ##     set_level='planning_structure_set',
        ##     set_type=None,
        ##     set_elements='planning_structure_preferences',
        ##     filename=row.PlanningStructureFile,
        ##     set_level_name=row.PlanningStructureWorkflow,
        ##     dialog=False,
        ##     folder=path_planning_structure_protocol,
        ##     verbose_logging=False)[0]
        
        continue
    sys.exit('Done')

    ## path = os.path.dirname(file_csv)
    ## output_filename = os.path.join(path, file_csv.replace(".csv","_output.txt"))
    ## output_file = open(output_filename, "a+")
    ## output_message = "PatientID" + "\tPlan Name" + "\tBeamSet Name" + "\tStatus\n"
    ## output_file.write(output_message)
    ## output_file.close()
    ## Get current patient, case, exam, and plan
    ## note that the interpreter handles a missing plan as an Exception
    ## patient = GeneralOperations.find_scope(level='Patient')
    ## case = GeneralOperations.find_scope(level='Case')
    ## exam = GeneralOperations.find_scope(level='Examination')
    # plan = GeneralOperations.find_scope(level='Plan')
    # Get in here and grab a patient specific csv
    ## protocol_folder = r'../protocols'
    ## institution_folder = r'UW'
    ## beamset_folder = ''
    ## file = 'UWGeneric.xml'
    ## protocol_beamset = 'Tomo3D-FW5'
    ## beamset_file = 'UWGeneric.xml'
    ## path_protocols = os.path.join(os.path.dirname(__file__),
    ##                             protocol_folder,
    ##                             institution_folder, beamset_folder)
    # Targets and dose
    ## target_1 = 'PTV_60'
    ## target_1_dose = 6000
    # target_2 = 'PTV_60'
    # target_2_dose = 6000
    # target_3 = 'PTV_54'
    # target_3_dose = 5400
    ## rx_target = target_1
    ## beamset_name = 'Tmplt_20Feb2020'
    ## number_fractions = 30
    ## machine = 'HDA0488'
    ## iso_target = 'All_PTVs'
    ## #
    ## planning_struct = True
    if planning_struct:
        # Define planning structures
        planning_prefs= StructureOperations.planning_structure_preferences()
        planning_prefs.number_of_targets = 1
        planning_prefs.use_uniform_dose = True
        planning_prefs.use_under_dose = False
        planning_prefs.use_inner_air = False

    dialog1_response = {'number_of_targets': 1,
                        'generate_underdose': False,
                        'generate_uniformdose': True,
                        'generate_inner_air': False}
    targets_dose = {target_1: target_1_dose}
    dialog2_response = targets_dose
    # dialog1_response = {'number_of_targets': 2,
    #                     'generate_underdose': False,
    #                     'generate_uniformdose': True,
    #                     'generate_inner_air': False}
    # targets_dose = {target_1: target_1_dose, target_2: target_2_dose, target_3: target_3_dose}
    # dialog2_response = targets_dose
    # dialog1_response = None
    # dialog2_response = None
    dialog3_response = {'structures': ['Bone_Mandible', 'Larynx', 'Esophagus'],
                        'standoff': 0.4}
    dialog4_response = {'structures': ['Bone_Mandible', 'Larynx', 'Esophagus'],
                        'standoff': 0.4}
    dialog5_response = {'target_skin': False,
                        'ring_hd': True,
                        'target_rings': True,
                        'thick_hd_ring': 2,
                        'thick_ld_ring': 5,
                        'ring_standoff': 0.2,
                        'otv_standoff': 0.4}
    StructureOperations.planning_structures(
        generate_ptvs=True,
        generate_ptv_evals=True,
        generate_otvs=True,
        generate_skin=True,
        generate_inner_air=True,
        generate_field_of_view=True,
        generate_ring_hd=True,
        generate_ring_ld=True,
        generate_normal_2cm=True,
        generate_combined_ptv=True,
        skin_contraction=0.3,
        run_status=False,
        planning_structure_selections=planning_prefs,
        dialog2_response=dialog2_response,
        dialog3_response=dialog3_response,
        dialog4_response=dialog4_response,
        dialog5_response=dialog5_response
    )

    # Dependancies: All_PTVs
    iso_target_exists = StructureOperations.check_structure_exists(
    case=case, structure_name=iso_target, option='Wait', exam=exam)
    if not iso_target_exists:
        logging.debug('{} does not exist. It must be defined to make this script work'.format(iso_target))
        sys.exit('{} is a required structure'.format(iso_target))

    # TODO: Add a plan based on the xml
    # Go grab the beamset called protocol_beamset
    # This step is likely not neccessary, just know exact beamset name from protocol
    available_beamsets = BeamOperations.Beams.select_element(
        set_level='beamset',
        set_type=None,
        set_elements='beam',
        filename=beamset_file,
        set_level_name=protocol_beamset,
        dialog=False,
        folder=path_protocols,
        verbose_logging=False)

    # TODO: Retrieve these definitions from the planning protocol.
    ## beamset_defs = BeamOperations.BeamSet()
    ## beamset_defs.rx_target = rx_target
    ## beamset_defs.name = beamset_name
    ## beamset_defs.DicomName = beamset_name
    ## beamset_defs.number_of_fractions = number_fractions
    ## beamset_defs.total_dose = target_1_dose
    ## beamset_defs.machine = machine
    ## beamset_defs.modality = 'Photons'
    ## beamset_defs.technique = 'TomoHelical'
    ## beamset_defs.iso_target = iso_target
    ## beamset_defs.protocol_name = available_beamsets

    order_name = None
    # par_beam_set = BeamOperations.beamset_dialog(case=case,
    #                                              filename=file,
    #                                              path=path_protocols,
    #                                              order_name=order_name)

    ## rs_beam_set = BeamOperations.create_beamset(patient=patient,
    ##                                             case=case,
    ##                                             exam=exam,
    ##                                             plan=plan,
    ##                                             dialog=False,
    ##                                             BeamSet=beamset_defs,
    ##                                             create_setup_beams=False)

    ##  beams = BeamOperations.load_beams_xml(filename=file,
    ##                                       beamset_name=protocol_beamset,
    ##                                       path=path_protocols)
    ## if len(beams) > 1:
    ##     logging.warning('Invalid tomo beamset in {}, more than one Tomo beam found.'.format(beamset_defs.name))
    ## else:
    ##     beam = beams[0]

    # Place isocenter
    ## try:
    ##     beamset_defs.iso = BeamOperations.find_isocenter_parameters(
    ##         case=case,
    ##         exam=exam,
    ##         beamset=rs_beam_set,
    ##         iso_target=beamset_defs.iso_target,
    ##         lateral_zero=True)
    ## except Exception:
    ##     logging.warning('Aborting, could not locate center of {}'.format(beamset_defs.iso_target))
    ##     sys.exit('Failed to place isocenter')

    ## BeamOperations.place_tomo_beam_in_beamset(plan=plan, iso=beamset_defs.iso, beamset=rs_beam_set, beam=beam)

    ## patient.Save()
    ## rs_beam_set.SetCurrent()
    ## sys.exit('Done')

    dialog_beamset.rx_target = dialog.values['0']
    dialog_beamset.name = dialog.values['1']
    dialog_beamset.DicomName = dialog.values['1']
    dialog_beamset.number_of_fractions = float(dialog.values['2'])
    dialog_beamset.total_dose = float(dialog.values['3'])
    dialog_beamset.machine = dialog.values['4']
    dialog_beamset.modality = 'Photons'
    dialog_beamset.technique = dialog.values['6']
    dialog_beamset.iso_target = dialog.values['7']
    dialog_beamset.protocol_name = dialog.values['8']
    # For debugging we can bypass the dialog by uncommenting the below lines
    order_name = None
    par_beam_set = BeamOperations.beamset_dialog(case=case,
                                                filename=file,
                                                path=path_protocols,
                                                order_name=order_name)

    rs_beam_set = BeamOperations.create_beamset(patient=patient,
                                                case=case,
                                                exam=exam,
                                                plan=plan,
                                                dialog=False,
                                                BeamSet=par_beam_set,
                                                create_setup_beams=False)

    beams = BeamOperations.load_beams_xml(filename=file,
                                        beamset_name=par_beam_set.protocol_name,
                                        path=path_protocols)

    # Now add in clinical goals and objectives
    add_goals_and_structures_from_protocol(patient=patient, case=case, plan=plan, beamset=rs_beam_set, exam=exam,
                                        filename=None, path_protocols=None, run_status=False)

if __name__ == '__main__':
    main()