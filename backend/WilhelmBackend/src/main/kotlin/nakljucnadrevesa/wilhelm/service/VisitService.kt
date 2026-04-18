package nakljucnadrevesa.wilhelm.service

import nakljucnadrevesa.wilhelm.dto.CreateVisitRequest
import nakljucnadrevesa.wilhelm.dto.VisitResponse
import nakljucnadrevesa.wilhelm.dto.toResponse
import nakljucnadrevesa.wilhelm.entity.Visit
import nakljucnadrevesa.wilhelm.exception.DocumentAlreadyExistsException
import nakljucnadrevesa.wilhelm.exception.DocumentNotFoundException
import nakljucnadrevesa.wilhelm.exception.DocumentStorageException
import nakljucnadrevesa.wilhelm.exception.VisitNotFoundException
import nakljucnadrevesa.wilhelm.repository.VisitRepository
import org.springframework.core.io.Resource
import org.springframework.core.io.UrlResource
import org.springframework.stereotype.Service
import org.springframework.web.multipart.MultipartFile
import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.time.LocalDate

enum class DocumentType {
    TRIAGE, REPORT, XRAY
}

@Service
class VisitService(
    private val visitRepository: VisitRepository,
    private val patientService: PatientService
) {

    fun createVisit(ehrId: String, request: CreateVisitRequest): VisitResponse {
        val patient = patientService.findOrThrow(ehrId)
        val visit = visitRepository.save(Visit(patient = patient, visitDate = request.visitDate))
        try {
            Files.createDirectories(visitFolder(ehrId, visit.id))
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to create folder for visit ${visit.id}", ex)
        }
        return visit.toResponse()
    }

    fun getVisitsForPatient(ehrId: String, date: LocalDate?): List<VisitResponse> {
        val patient = patientService.findOrThrow(ehrId)
        return if (date != null) {
            visitRepository.findByPatientAndVisitDate(patient, date)
        } else {
            visitRepository.findByPatient(patient)
        }.map { it.toResponse() }
    }

    fun getVisit(visitId: Long): VisitResponse =
        findOrThrow(visitId).toResponse()

    fun uploadDocument(visitId: Long, type: DocumentType, file: MultipartFile): VisitResponse {
        val visit = findOrThrow(visitId)
        val folder = visitFolder(visit.patient.ehrId, visitId)
        val filename = file.originalFilename ?: "file"
        val existingFiles = when (type) {
            DocumentType.TRIAGE -> visit.triageFiles
            DocumentType.REPORT -> visit.reportFiles
            DocumentType.XRAY   -> visit.xrayFiles
        }.toFileList()
        if (existingFiles.contains(filename)) {
            throw DocumentAlreadyExistsException(filename, visitId)
        }
        try {
            Files.createDirectories(folder)
            file.transferTo(folder.resolve(filename).toFile())
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to store $filename for visit $visitId", ex)
        }
        when (type) {
            DocumentType.TRIAGE -> visit.triageFiles = visit.triageFiles.appendFilename(filename)
            DocumentType.REPORT -> visit.reportFiles = visit.reportFiles.appendFilename(filename)
            DocumentType.XRAY   -> visit.xrayFiles   = visit.xrayFiles.appendFilename(filename)
        }
        return visitRepository.save(visit).toResponse()
    }

    fun downloadDocument(visitId: Long, type: DocumentType, filename: String): Resource {
        val visit = findOrThrow(visitId)
        val fileList = when (type) {
            DocumentType.TRIAGE -> visit.triageFiles
            DocumentType.REPORT -> visit.reportFiles
            DocumentType.XRAY   -> visit.xrayFiles
        }
        if (!fileList.split(",").contains(filename)) {
            throw DocumentNotFoundException(visitId, filename)
        }
        val file = visitFolder(visit.patient.ehrId, visitId).resolve(filename)
        if (!Files.exists(file)) {
            throw DocumentNotFoundException(visitId, filename)
        }
        return try {
            UrlResource(file.toUri())
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to read $filename for visit $visitId", ex)
        }
    }

    fun deleteVisit(visitId: Long) {
        val visit = findOrThrow(visitId)
        try {
            visitFolder(visit.patient.ehrId, visitId).toFile().deleteRecursively()
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to delete folder for visit $visitId", ex)
        }
        visitRepository.delete(visit)
    }

    private fun visitFolder(ehrId: String, visitId: Long): Path =
        patientService.patientFolder(ehrId).resolve(visitId.toString())

    private fun findOrThrow(visitId: Long): Visit =
        visitRepository.findById(visitId)
            .orElseThrow { VisitNotFoundException(visitId) }

    private fun String.toFileList(): List<String> =
        if (isBlank()) emptyList() else split(",")

    private fun String.appendFilename(filename: String): String =
        if (isBlank()) filename else "$this,$filename"
}
