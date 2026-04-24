package com.iams.app.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.BottomSheetDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary

enum class LegalDocument { TERMS_OF_SERVICE, PRIVACY_POLICY }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LegalDocumentSheet(
    document: LegalDocument,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = Background,
        dragHandle = { BottomSheetDefaults.DragHandle() }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .heightIn(min = 320.dp)
        ) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = when (document) {
                        LegalDocument.TERMS_OF_SERVICE -> "Terms of Service"
                        LegalDocument.PRIVACY_POLICY -> "Privacy Policy"
                    },
                    style = MaterialTheme.typography.headlineSmall.copy(
                        fontWeight = FontWeight.Bold,
                        fontSize = 22.sp
                    ),
                    color = Primary
                )
            }

            Text(
                text = "Last updated: April 2026",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(horizontal = 24.dp)
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Scrollable content
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp)
                    .padding(bottom = 32.dp)
            ) {
                when (document) {
                    LegalDocument.TERMS_OF_SERVICE -> TermsOfServiceContent()
                    LegalDocument.PRIVACY_POLICY -> PrivacyPolicyContent()
                }
            }
        }
    }
}

@Composable
private fun TermsOfServiceContent() {
    LegalSection(
        title = "1. Acceptance of Terms",
        body = "By creating an account and using the IAMS (Intelligent Attendance Monitoring System) mobile application, you agree to be bound by these Terms of Service. If you do not agree, please do not use the application."
    )
    LegalSection(
        title = "2. Eligibility",
        body = "IAMS is intended for enrolled students and authorized faculty of Jose Rizal Memorial State University (JRMSU). You must provide a valid Student ID or faculty credentials to register."
    )
    LegalSection(
        title = "3. Account Responsibility",
        body = "You are responsible for maintaining the confidentiality of your login credentials and for all activities that occur under your account. Notify the administrator immediately of any unauthorized use."
    )
    LegalSection(
        title = "4. Acceptable Use",
        body = "You agree to use IAMS only for its intended purpose: attendance monitoring and related academic activities. You will not attempt to tamper with the facial recognition system, submit false biometric data, or use another person's account."
    )
    LegalSection(
        title = "5. Face Registration",
        body = "Registering your face is required for attendance recognition. You confirm that the images you submit are of yourself and accurately represent your likeness. Fraudulent submissions may result in account suspension and academic disciplinary action."
    )
    LegalSection(
        title = "6. System Availability",
        body = "While we strive for continuous availability, IAMS may be unavailable due to maintenance, network issues, or circumstances beyond our control. We are not liable for attendance discrepancies caused by technical outages; fallback procedures may be coordinated with your instructor."
    )
    LegalSection(
        title = "7. Modifications",
        body = "These terms may be updated from time to time. Continued use of the application after changes constitutes acceptance of the revised terms."
    )
    LegalSection(
        title = "8. Termination",
        body = "Accounts may be deactivated upon graduation, withdrawal, or violation of these terms. Deactivated accounts lose access to the application and related data."
    )
    LegalSection(
        title = "9. Contact",
        body = "For questions regarding these terms, please contact the JRMSU IAMS administrator through your department office."
    )
}

@Composable
private fun PrivacyPolicyContent() {
    LegalSection(
        title = "1. Information We Collect",
        body = "We collect the following information when you use IAMS:\n\n• Identity details: name, Student ID, JRMSU email, date of birth.\n• Biometric data: facial images captured during registration, and facial embeddings (mathematical vectors) derived from those images.\n• Attendance data: timestamps, classroom, and recognition results generated during class sessions.\n• Device data: authentication tokens and basic device metadata required to keep your session active."
    )
    LegalSection(
        title = "2. How We Use Your Information",
        body = "Your information is used to:\n\n• Verify your identity and authorize access to the application.\n• Recognize your face during class sessions and record attendance automatically.\n• Provide faculty and administrators with accurate attendance reports.\n• Troubleshoot and improve the system."
    )
    LegalSection(
        title = "3. Biometric Data",
        body = "Face images are converted into non-reversible embeddings used for matching. The original images and embeddings are stored on JRMSU-controlled servers and are never sold or shared with third parties for advertising or commercial purposes. They are used strictly for attendance monitoring within JRMSU."
    )
    LegalSection(
        title = "4. Data Sharing",
        body = "Attendance results are visible to:\n\n• Yourself, within the application.\n• The instructor of the class in which you are enrolled.\n• Authorized JRMSU administrators.\n\nWe do not share your personal or biometric information with any party outside JRMSU, except when required by law."
    )
    LegalSection(
        title = "5. Data Retention",
        body = "Attendance records are retained for the duration of your enrollment and in accordance with JRMSU's academic records policy. Biometric data is retained while your account is active and is deleted or anonymized upon account deactivation."
    )
    LegalSection(
        title = "6. Security",
        body = "We apply reasonable technical and organizational safeguards including encrypted connections (HTTPS/WSS), access controls, and restricted server access. No system is perfectly secure; we will notify affected users in the event of a data breach in line with applicable regulations."
    )
    LegalSection(
        title = "7. Your Rights",
        body = "You may request to:\n\n• Review the personal information we hold about you.\n• Correct inaccurate information.\n• Delete your biometric data (note: this will prevent attendance recognition).\n\nRequests can be made through the JRMSU IAMS administrator."
    )
    LegalSection(
        title = "8. Children's Privacy",
        body = "IAMS is not intended for users under 13. Users under 18 must have parental or guardian consent consistent with JRMSU enrollment requirements."
    )
    LegalSection(
        title = "9. Changes to This Policy",
        body = "We may update this Privacy Policy as the system evolves. Significant changes will be announced through the application or by JRMSU official channels."
    )
    LegalSection(
        title = "10. Contact",
        body = "For questions or requests regarding your data, please reach out to the JRMSU IAMS administrator."
    )
}

@Composable
private fun LegalSection(title: String, body: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.bodyLarge.copy(
            fontWeight = FontWeight.SemiBold,
            lineHeight = 22.sp
        ),
        color = Primary
    )
    Spacer(modifier = Modifier.height(6.dp))
    Text(
        text = body,
        style = MaterialTheme.typography.bodyMedium.copy(lineHeight = 22.sp),
        color = TextSecondary
    )
    Spacer(modifier = Modifier.height(18.dp))
}
