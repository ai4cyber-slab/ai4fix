import xml.etree.ElementTree as ET
import json

file_path = r"path_to_spotbugs_json\spotbugs_dangerous_vulnerable_methods.json"

def count_sast_warnings_from_file(file_path, original_library):
    try:
        with open(file_path, 'r') as file:
            if file.readable() and not file.read(1):
                return "Error: The file is empty."
            
            file.seek(0)
            data = json.load(file)
        
        warning_types = {}
        total_warnings = 0

        for warning in data:
            warning_type = warning.get('warning_type')
            total_warnings += 1
            if warning_type in warning_types:
                warning_types[warning_type] += 1
            else:
                warning_types[warning_type] = 1

        warning_types_str = ', '.join([f"'{k}': {v}" for k, v in warning_types.items()])
        
        differences = {}
        all_warning_types = set(warning_types.keys()).union(original_library.keys())

        for warning_type in all_warning_types:
            original_count = original_library.get(warning_type, 0)
            current_count = warning_types.get(warning_type, 0)
            if original_count != current_count:
                differences[warning_type] = current_count - original_count

        differences_str = ', '.join([f"'{k}': {v}" for k, v in differences.items()])

        # Print the formatted strings
        print(f"Total Warnings: {total_warnings}")
        #print("Warning Types Count:")
        #print(warning_types_str)
        print("Differences from Original Library:")
        print(differences_str)

        return total_warnings, warning_types, differences

    except FileNotFoundError:
        return "Error: The file was not found."
    except json.JSONDecodeError as e:
        return f"Error: The JSON is not well-formed. Details: {str(e)}"



#all spotbugs warnings
original_library_all = {
'EI_EXPOSE_REP': 122, 'SE_BAD_FIELD': 61, 'SE_NO_SERIALVERSIONID': 70, 'UWF_FIELD_NOT_INITIALIZED_IN_CONSTRUCTOR': 128, 'CN_IMPLEMENTS_CLONE_BUT_NOT_CLONEABLE': 1, 
'EI_EXPOSE_REP2': 200, 'SE_TRANSIENT_FIELD_NOT_RESTORED': 5, 'SIC_INNER_SHOULD_BE_STATIC_ANON': 22, 'DCN_NULLPOINTER_EXCEPTION': 2, 'NP_NULL_ON_SOME_PATH': 1, 
'RCN_REDUNDANT_NULLCHECK_WOULD_HAVE_BEEN_A_NPE': 3, 'URF_UNREAD_PUBLIC_OR_PROTECTED_FIELD': 12, 'CI_CONFUSED_INHERITANCE': 5, 'IS2_INCONSISTENT_SYNC': 4, 'SE_INNER_CLASS': 8, 
'UCF_USELESS_CONTROL_FLOW': 1, 'REC_CATCH_EXCEPTION': 21, 'RCN_REDUNDANT_NULLCHECK_OF_NONNULL_VALUE': 58, 'SF_SWITCH_NO_DEFAULT': 3, 'DM_CONVERT_CASE': 14, 'DM_FP_NUMBER_CTOR': 2, 
'DM_NUMBER_CTOR': 2, 'DM_BOXED_PRIMITIVE_FOR_PARSING': 1, 'PZLA_PREFER_ZERO_LENGTH_ARRAYS': 17, 'CT_CONSTRUCTOR_THROW': 24, 'URF_UNREAD_FIELD': 1, 
'VSC_VULNERABLE_SECURITY_CHECK_METHODS': 3, 'DP_DO_INSIDE_DO_PRIVILEGED': 2, 'MC_OVERRIDABLE_METHOD_CALL_IN_READ_OBJECT': 2, 'UWF_UNWRITTEN_FIELD': 1, 
'HE_HASHCODE_NO_EQUALS': 1, 'NP_EQUALS_SHOULD_HANDLE_NULL_ARGUMENT': 5, 'HE_EQUALS_USE_HASHCODE': 2, 'DM_STRING_CTOR': 1,
'AA_ASSERTION_OF_ARGUMENTS': 2, 'UUF_UNUSED_FIELD': 1, 'IA_AMBIGUOUS_INVOCATION_OF_INHERITED_OR_OUTER_METHOD': 1, 'BC_UNCONFIRMED_CAST': 57, 'DE_MIGHT_IGNORE': 1, 
'MS_PKGPROTECT': 3, 'DL_SYNCHRONIZATION_ON_SHARED_CONSTANT': 1, 'JLM_JSR166_UTILCONCURRENT_MONITORENTER': 1, 'RV_RETURN_VALUE_OF_PUTIFABSENT_IGNORED': 2, 
'MS_SHOULD_BE_REFACTORED_TO_BE_FINAL': 1, 'IM_BAD_CHECK_FOR_ODD': 1, 'DMI_COLLECTION_OF_URLS': 4, 'NP_NULL_ON_SOME_PATH_FROM_RETURN_VALUE': 3, 'RR_NOT_CHECKED': 1, 
'DP_CREATE_CLASSLOADER_INSIDE_DO_PRIVILEGED': 4, 'BC_UNCONFIRMED_CAST_OF_RETURN_VALUE': 9, 'DM_DEFAULT_ENCODING': 8, 'IC_SUPERCLASS_USES_SUBCLASS_DURING_INITIALIZATION': 1, 
'DM_BOOLEAN_CTOR': 1, 'BC_VACUOUS_INSTANCEOF': 1, 'MC_OVERRIDABLE_METHOD_CALL_IN_CONSTRUCTOR': 2, 'MS_SHOULD_BE_FINAL': 2, 'RC_REF_COMPARISON_BAD_PRACTICE_BOOLEAN': 1, 
'UUF_UNUSED_PUBLIC_OR_PROTECTED_FIELD': 1, 'NM_CONFUSING': 5, 'NM_FIELD_NAMING_CONVENTION': 1, 'UPM_UNCALLED_PRIVATE_METHOD': 1, 'MF_CLASS_MASKS_FIELD': 2, 
'RI_REDUNDANT_INTERFACES': 4, 'RV_RETURN_VALUE_IGNORED_BAD_PRACTICE': 2, 'WMI_WRONG_MAP_ITERATOR': 2, 'NM_SAME_SIMPLE_NAME_AS_INTERFACE': 6, 
'RV_RETURN_VALUE_IGNORED_NO_SIDE_EFFECT': 1, 'SBSC_USE_STRINGBUFFER_CONCATENATION': 1, 'SE_BAD_FIELD_STORE': 1, 'NO_NOTIFY_NOT_NOTIFYALL': 2, 'NM_SAME_SIMPLE_NAME_AS_SUPERCLASS': 1,
'NP_LOAD_OF_KNOWN_NULL_VALUE': 1, 'IT_NO_SUCH_ELEMENT': 1, 'MS_CANNOT_BE_FINAL': 1, 'ST_WRITE_TO_STATIC_FROM_INSTANCE_METHOD': 1
}

#100 spotbugs warnings from json
original_library = {
    "CT_CONSTRUCTOR_THROW" : 3,
    "DP_DO_INSIDE_DO_PRIVILEGED" : 2,
    "SE_BAD_FIELD" : 19,
    "SE_NO_SERIALVERSIONID" : 6,
    "VSC_VULNERABLE_SECURITY_CHECK_METHODS" : 3,
    "EI_EXPOSE_REP2" : 27,
    "SIC_INNER_SHOULD_BE_STATIC_ANON" : 1,
    "URF_UNREAD_PUBLIC_OR_PROTECTED_FIELD" : 1,
    "UWF_FIELD_NOT_INITIALIZED_IN_CONSTRUCTOR" : 22,
    "EI_EXPOSE_REP" : 13,
    "URF_UNREAD_FIELD" : 1,
    "RCN_REDUNDANT_NULLCHECK_WOULD_HAVE_BEEN_A_NPE" : 1,
    "BC_UNCONFIRMED_CAST" : 1,
}

result = count_sast_warnings_from_file(file_path, original_library)

if isinstance(result, tuple):
    total_warnings, warning_types, differences = result
else:
    print(result)