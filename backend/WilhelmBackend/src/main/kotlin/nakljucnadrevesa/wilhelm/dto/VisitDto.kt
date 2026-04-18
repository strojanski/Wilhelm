package nakljucnadrevesa.wilhelm.dto

import nakljucnadrevesa.wilhelm.entity.Visit
import java.time.Instant
import java.time.LocalDate

data class CreateVisitRequest(
    val visitDate: LocalDate
)

data class VisitResponse(
    val id: Long,
    val patientEhrId: String,
    val visitDate: LocalDate,
    val createdAt: Instant,
    val triageFiles: List<String>,
    val reportFiles: List<String>,
    val xrayFiles: List<String>
)

fun Visit.toResponse() = VisitResponse(
    id = id,
    patientEhrId = patient.ehrId,
    visitDate = visitDate,
    createdAt = createdAt,
    triageFiles = triageFiles.toFileList(),
    reportFiles = reportFiles.toFileList(),
    xrayFiles   = xrayFiles.toFileList()
)

private fun String.toFileList(): List<String> =
    if (isBlank()) emptyList() else split(",")
