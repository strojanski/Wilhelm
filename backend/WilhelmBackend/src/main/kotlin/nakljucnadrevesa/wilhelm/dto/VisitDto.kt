package nakljucnadrevesa.wilhelm.dto

import nakljucnadrevesa.wilhelm.entity.Visit
import java.time.Instant
import java.time.LocalDate

data class CreateVisitRequest(
    val visitDate: LocalDate
)

data class FractureSegment(
    val annId: Int,
    val bbox: List<Int>,       // [x1, y1, x2, y2]
    val iouScore: Double,
    val userCorrected: Boolean = false,
    val maskB64: String? = null  // base64-encoded PNG mask from SAM-Med2D
)

data class XrayAnalysis(
    val segments: List<FractureSegment>,
    val analyzedAt: Instant = Instant.now(),
    val corrected: Boolean = false
)

data class SaveAnnotationsRequest(
    val segments: List<FractureSegment>
)

data class VisitResponse(
    val id: Long,
    val patientEhrId: String,
    val visitDate: LocalDate,
    val createdAt: Instant,
    val triageFiles: List<String>,
    val reportFiles: List<String>,
    val xrayFiles: List<String>,
    val xrayAnnotations: Map<String, XrayAnalysis>
)

private fun String.toFileList(): List<String> =
    if (isBlank()) emptyList() else split(",")
