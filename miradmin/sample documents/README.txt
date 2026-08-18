NORTHWOOD ONBOARDING SAMPLE EVIDENCE PACK
=========================================

Purpose
-------
This pack gives one structured evidence template for each onboarding checklist item, plus supporting security-review files and an X12-style sample 835.

How to use
----------
1. Open the file for the checklist item.
2. Replace every required {{TOKEN}} with a real value.
3. Keep the surrounding field labels and structure unchanged if your project validates by label/pattern.
4. Set/retain the status as Complete / Accepted / Passed where applicable.
5. Upload the evidence file to the corresponding checklist item.

Recommended validation rule
---------------------------
SUCCESS when:
- expected file exists;
- all required fields are present;
- required values are non-empty;
- no required {{TOKEN}} remains;
- status is Complete/Accepted/Passed as expected;
- required dates/emails use valid syntax;
- for item 11, MPL result must be Accepted;
- for item 13, all critical go-live checks must be Passed.

IMPORTANT
---------
The NDA and BAA are sample structures, not legal advice or final legal forms. Replace with counsel-approved documents for real production use.
The security assurance files are sample evidence structures, not actual certifications or audit reports.
The 835 contains obvious test values and placeholder business fields. It is intended for parser/mapping testing, not payment processing.

Files
-----
- 835_to_MIR_Mapping_Notes.pdf
- BAA_Northwood_20250805.pdf
- Claims_System_Identification.pdf
- Delivery_Method_Agreement.pdf
- First_Production_Delivery_Record.pdf
- Go_Live_Checks.pdf
- HIPAA_Audit_Letter_SAMPLE.pdf
- ISO27001_Certificate_SAMPLE.pdf
- MPL_Test_File_Acceptance.pdf
- NDA_Northwood_20250804.pdf
- Named_Contacts_Record.pdf
- Portal_Walkthrough_Record.pdf
- SOC2_Report_SAMPLE.pdf
- Sample_835_Northwood.edi
- Sample_835_Receipt_Record.pdf
- Security_Review_Returned_to_Client.pdf
- Subprocessor_List_SAMPLE.pdf
- Test_Conversion_Client_Review.pdf
- Test_Environment_Record.pdf
- example_placeholder_values.json
- validation_manifest.json
