"""Apply the approved design revision while preserving untouched OOXML parts.

Run with bundled Python from the project parent. Output is a candidate, not an
automatic overwrite. Layout verification must precede replacing the main DOCX.
"""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'BACS3403_FinalDoc_TanRiLi.docx'
OUT = ROOT / 'MyFYP/tmp/docx/approved-design.docx'
BACKUP = ROOT / 'report-backups/BACS3403_FinalDoc_TanRiLi.before-design-alignment.docx'
EXPECTED = 'd5920f36d0e730dc8368c4cceff9a9ed94bc8990e30d7b2759d85a71014168bd'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# Paragraph numbers refer to the verified supplied version, including tables.
REPLACEMENTS = {
94: 'The Smart Skin Health System is proposed as an educational hospital platform combining skin image assessment with hospital management functions. It aims to help patients record skin concerns and prepare for consultations while supporting administrative workflows. The project will be implemented incrementally and evaluated as a final-year prototype. It is not intended to replace professional clinical assessment, and improvements in diagnosis rates or operational efficiency have not yet been measured.',
96: 'The methodology follows the Incremental Model with testing and feedback after each connected workflow. The approved stack uses React Native with Expo and TypeScript for the Android patient app, Next.js with TypeScript for the management dashboard, and one shared Python backend for application logic and AI inference. Supabase is planned for authentication, PostgreSQL and private file storage. Model fine-tuning and evaluation form a separate development workflow. Testing will cover functionality, persistence, access control, usability and model performance.',
97: 'Implementation and evaluation have not yet been completed. The first preview will demonstrate skin-photo submission and history, appointment booking, patient queue updates, prescriptions and billing using shared saved records. AI predictions and payment processing will be clearly simulated. All nine modules remain in the final project scope. Claims about model accuracy, clinical reliability, patient willingness or reduced workload will require evidence from subsequent evaluation.',
253: 'Development follows the Incremental Model shown in Figure 1.1. Each increment delivers a connected workflow that can be tested before further functions are added. The tentative preview on 22 October 2026 prioritises skin-photo assessment and history, appointment booking, patient queues, prescriptions and billing, with shared saved records between the Android app and management dashboard. AI predictions and payment processing will be simulated at this milestone. Account management, user management, registration, AI assessment, medical records, pharmacy, billing, feedback and reporting all remain in the final scope. Later increments replace simulations and complete remaining functions; the final deadline is to be confirmed.',
624: 'For this project, React Native with Expo and TypeScript is selected for the patient application. The initial testing target is an Android phone using Expo Go. Expo ImagePicker provides camera and gallery access for photo submission. This selection follows the requirements for low setup effort, incremental development and a common TypeScript language across the mobile and web interfaces; it does not establish that React Native outperforms every alternative. Flutter and native development remain valid alternatives in the preceding comparison. The Doctor, Staff and Admin dashboard will use Next.js, TypeScript, Tailwind CSS and shadcn/ui. The interfaces share data contracts and validation rules while retaining platform-appropriate screens. A shared Python backend will handle application operations and AI inference, avoiding duplicate business APIs in Next.js. Expo Go is a testing host; a separately installable Android APK requires a later build and verification step. App-store publication is a separate activity. Custom native integrations may require a development build rather than Expo Go.',
682: 'The patient app will use React Native, Expo and TypeScript, initially tested on Android through Expo Go. Expo ImagePicker will provide camera and gallery access. The web management dashboard for Doctor, Staff and Admin will use Next.js and TypeScript. These interfaces will share data definitions and use the same saved records, while camera permissions, cancellation and platform-specific navigation will be tested separately.',
684: 'One shared Python backend will serve the Android app and web dashboard, handling application operations and AI inference. Supabase is planned to provide managed authentication, PostgreSQL and private file storage. No separate Node.js business API is planned. Model training and fine-tuning will run as reproducible development tasks. The model framework and preprocessing pipeline will be selected after checking dataset suitability, licences and evaluation requirements; successful prediction has not yet been demonstrated.',
686: 'The architecture separates the Android interface, management dashboard, shared Python application backend and managed data services. This allows interfaces to evolve without duplicating business rules. Database schemas and access policies will be versioned, and sensitive operations will be authorised on the backend. Shared-record workflows will be tested incrementally. Hosting capacity, model latency, storage limits and deployment costs remain to be verified before claiming scalability or production readiness.',
710: 'The project will prioritise open-source development tools, local testing and synthetic demonstration data to control initial costs. Managed hosting, authentication, image storage and model inference may introduce usage limits or charges; these will be checked before deployment. A shared backend avoids maintaining separate business APIs for the mobile and web interfaces. Actual reductions in operating costs, missed appointments or wasted stock have not yet been measured and will not be claimed as completed results.',
4552: 'The planned role-based access model distinguishes Patient, Doctor, Staff and Admin. Patients access their own records. Doctors access records explicitly shared by a patient or authorised through a booked visit. Staff receive only the queue, prescription and billing information needed for assigned tasks, without general access to private clinical notes or photos. Admins manage accounts and permitted reports but do not automatically gain access to all clinical content. Backend checks must enforce these boundaries; users must not grant themselves privileged roles. Access grants, changes and sensitive operations will be auditable. These controls are approved design requirements, not verified implementation results.',
4718: 'The AI assessment module is planned to suggest possible common skin conditions from patient images. The initial preview will return clearly labelled simulated results, independent of model training. A later implementation will integrate an evaluated fine-tuned model through the shared Python backend. The following stages describe planned work; no trained model, measured accuracy or clinical diagnostic reliability is claimed.',
4721: 'Patients will capture or select a skin photo in the React Native and Expo application using ImagePicker. The interface will guide lighting and focus, preview the image, handle cancellation and permission denial, and validate accepted JPEG/PNG files. The report retains a proposed minimum resolution of 224x224 pixels; final input dimensions will match the chosen model. Saving and any image transfer must follow patient consent and private-storage rules. Automated image-quality or body-region assessment must not be displayed as measured functionality until implemented and tested.',
4724: 'Preprocessing will follow the input specification used to train the selected model, including resizing and normalisation where required. The implementation will record the exact transformations and apply the same pipeline during training and inference. Blur, contrast enhancement, grayscale conversion or masking will be evaluated before adoption rather than assumed to improve predictions. Framework and preprocessing choices remain subject to dataset and model selection. The simulated preview does not perform medical feature extraction or classification.',
4727: 'A suitable pretrained backbone, potentially MobileNetV2 or EfficientNetB0, will be adapted and fine-tuned on a legally usable dataset whose labels and image type support the selected common skin conditions. Exact prediction classes and dataset sources are not yet fixed. Candidate data must be assessed for annotation quality, class balance, patient overlap and suitability for ordinary phone photographs. Fine-tuning effort will be documented through preprocessing, training configuration, reproducible data splits and comparison with a baseline. Held-out evaluation will report per-class metrics, a confusion matrix and limitations. The preview uses simulated labels and does not claim trained predictions.',
4730: 'The real model, once evaluated, will return possible condition labels and model scores separately from any doctor findings. Scores indicate model output and must not be treated as medical severity. The previous rule assigning High Risk solely from confidence above 85 percent is removed. Any future risk assessment requires a separately justified approach and evaluation. Unsupported or uncertain inputs should not receive unwarranted reassurance. Preview results will be labelled simulated and include no claimed medical interpretation of the submitted photo. Real outputs will remain educational and must not replace professional assessment; all claimed results and limitations will be reported from actual testing.',
4839: 'The planned patient interface uses React Native, Expo and TypeScript, with Android as the initial test platform. The management dashboard for Doctor, Staff and Admin uses Next.js and TypeScript. Both interfaces use one shared Python backend for application operations and AI inference, while Supabase is planned for managed authentication, PostgreSQL and private file storage. No separate Node.js business API is required. Model development will adapt pretrained weights through documented fine-tuning and evaluation on suitable licensed common-condition data. The first preview includes skin-photo assessment/history, booking, queues, prescriptions and billing with shared saved records; AI predictions and payment processing are simulated. All nine final modules remain in scope. Expo Go testing, standalone APK building and app-store publication are separate stages. The system is an educational prototype, and implementation, model accuracy and clinical reliability are not yet established.',
}

def main():
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != EXPECTED:
        raise RuntimeError('Source changed since inspection; review before applying.')
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP.exists():
        if hashlib.sha256(BACKUP.read_bytes()).hexdigest() != EXPECTED:
            raise RuntimeError('Existing backup differs; refusing to overwrite.')
    else:
        shutil.copy2(SOURCE, BACKUP)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    changes = []
    with ZipFile(SOURCE) as source:
        root = etree.fromstring(source.read('word/document.xml'))
        paras = root.xpath('//w:body//w:p', namespaces=NS)
        for index, new in REPLACEMENTS.items():
            p = paras[index]
            if p.xpath('.//w:drawing | .//w:fldChar', namespaces=NS):
                raise RuntimeError(f'Paragraph {index} contains objects/fields.')
            ts = p.xpath('.//w:t', namespaces=NS)
            old = ''.join(t.text or '' for t in ts)
            if not old or not ts:
                raise RuntimeError(f'Empty paragraph {index}.')
            ts[0].text = new
            for t in ts[1:]:
                t.text = ''
            changes.append({'paragraph_index': index, 'before': old, 'after': new})
        xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        with ZipFile(OUT, 'w') as dest:
            for entry in source.infolist():
                dest.writestr(entry, xml if entry.filename == 'word/document.xml' else source.read(entry.filename))
    (OUT.parent / 'alignment-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding='utf-8')
    with ZipFile(SOURCE) as a, ZipFile(OUT) as b:
        assert a.namelist() == b.namelist()
        for name in a.namelist():
            if name != 'word/document.xml':
                assert a.read(name) == b.read(name), name
    print(f'Candidate prepared: {len(changes)} paragraphs; all other package parts unchanged.')
    print(f'Backup preserved: {BACKUP}')

if __name__ == '__main__':
    main()
