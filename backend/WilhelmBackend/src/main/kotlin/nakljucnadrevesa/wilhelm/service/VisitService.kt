package nakljucnadrevesa.wilhelm.service

import com.fasterxml.jackson.annotation.JsonProperty
import tools.jackson.databind.ObjectMapper
import tools.jackson.module.kotlin.readValue
import nakljucnadrevesa.wilhelm.dto.CreateVisitRequest
import nakljucnadrevesa.wilhelm.dto.FractureSegment
import nakljucnadrevesa.wilhelm.dto.SaveAnnotationsRequest
import nakljucnadrevesa.wilhelm.dto.VisitResponse
import nakljucnadrevesa.wilhelm.dto.XrayAnalysis
import nakljucnadrevesa.wilhelm.entity.Visit
import nakljucnadrevesa.wilhelm.exception.DocumentAlreadyExistsException
import nakljucnadrevesa.wilhelm.exception.DocumentNotFoundException
import nakljucnadrevesa.wilhelm.exception.DocumentStorageException
import nakljucnadrevesa.wilhelm.exception.VisitNotFoundException
import nakljucnadrevesa.wilhelm.repository.VisitRepository
import org.springframework.beans.factory.annotation.Value
import org.springframework.core.io.Resource
import org.springframework.core.io.UrlResource
import org.springframework.http.HttpEntity
import org.springframework.http.HttpHeaders
import org.springframework.http.MediaType
import org.springframework.stereotype.Service
import org.springframework.web.client.RestTemplate
import org.springframework.web.multipart.MultipartFile
import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant
import java.time.LocalDate

enum class DocumentType {
    TRIAGE, REPORT, XRAY
}

private data class AiSegment(
    @JsonProperty("ann_id")    val annId: Int,
    @JsonProperty("bbox")      val bbox: List<Int>,
    @JsonProperty("iou_score") val iouScore: Double,
    @JsonProperty("mask_b64")  val maskB64: String? = null,
)

private data class AiResponse(
    @JsonProperty("segments")           val segments: List<AiSegment>,
    @JsonProperty("prob_fracture")      val probFracture: Double = 0.0,
    @JsonProperty("predicted_fracture") val predictedFracture: Boolean = false,
)

@Service
class VisitService(
    private val visitRepository: VisitRepository,
    private val patientService: PatientService,
    private val objectMapper: ObjectMapper,
    @Value("\${app.ai.api-url:http://localhost:8000}") private val aiApiUrl: String,
    @Value("\${app.base-url:http://localhost:8080}") private val baseUrl: String,
) {

    fun createVisit(ehrId: String, request: CreateVisitRequest): VisitResponse {
        val patient = patientService.findOrThrow(ehrId)
        val visit = visitRepository.save(Visit(patient = patient, visitDate = request.visitDate))
        try {
            Files.createDirectories(visitFolder(ehrId, visit.id))
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to create folder for visit ${visit.id}", ex)
        }
        return visit.toVisitResponse()
    }

    fun getVisitsForPatient(ehrId: String, date: LocalDate?): List<VisitResponse> {
        val patient = patientService.findOrThrow(ehrId)
        return if (date != null) {
            visitRepository.findByPatientAndVisitDate(patient, date)
        } else {
            visitRepository.findByPatient(patient)
        }.map { it.toVisitResponse() }
    }

    fun getVisit(visitId: Long): VisitResponse =
        findOrThrow(visitId).toVisitResponse()

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
        return visitRepository.save(visit).toVisitResponse()
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

    fun analyzeXray(ehrId: String, visitId: Long, filename: String): VisitResponse {
        val visit = findOrThrow(visitId)
        if (!visit.xrayFiles.toFileList().contains(filename)) {
            throw DocumentNotFoundException(visitId, filename)
        }

        val imageUrl = "$baseUrl/api/patients/$ehrId/visits/$visitId/xray/$filename"
        println("Calling AI API at $aiApiUrl/analyze-url with image_url: $imageUrl")
        val rest = RestTemplate()
        val headers = HttpHeaders().also { it.contentType = MediaType.APPLICATION_JSON }
        val body = mapOf("image_url" to imageUrl)
        val entity = HttpEntity(body, headers)

        val aiResponse = try {
            rest.postForObject("$aiApiUrl/analyze-url", entity, AiResponse::class.java)
                ?: throw DocumentStorageException("Empty response from AI API")
        } catch (ex: Exception) {
            throw DocumentStorageException("Failed to call AI API: ${ex.message}", ex)
        }

        val segments = aiResponse.segments.map { s ->
            FractureSegment(
                annId         = s.annId,
                bbox          = s.bbox,
                iouScore      = s.iouScore,
                userCorrected = false,
                maskB64       = s.maskB64,
            )
        }

        val analysis = XrayAnalysis(
            segments   = segments,
            analyzedAt = Instant.now(),
            corrected  = false,
        )

        val annotations = parseAnnotations(visit.xrayAnnotations).toMutableMap()
        annotations[filename] = analysis
        visit.xrayAnnotations = objectMapper.writeValueAsString(annotations)
        return visitRepository.save(visit).toVisitResponse()
    }

    fun saveAnnotations(visitId: Long, filename: String, req: SaveAnnotationsRequest): VisitResponse {
        val visit = findOrThrow(visitId)
        if (!visit.xrayFiles.toFileList().contains(filename)) {
            throw DocumentNotFoundException(visitId, filename)
        }

        val analysis = XrayAnalysis(
            segments   = req.segments,
            analyzedAt = Instant.now(),
            corrected  = true,
        )

        val annotations = parseAnnotations(visit.xrayAnnotations).toMutableMap()
        annotations[filename] = analysis
        visit.xrayAnnotations = objectMapper.writeValueAsString(annotations)
        return visitRepository.save(visit).toVisitResponse()
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

    private fun parseAnnotations(json: String): Map<String, XrayAnalysis> =
        try {
            objectMapper.readValue(json)
        } catch (ex: Exception) {
            println("ERROR parsing annotations: ${ex.message}")
            ex.printStackTrace()
            emptyMap()
        }

    private fun Visit.toVisitResponse(): VisitResponse {
        val annotations = parseAnnotations(xrayAnnotations)
        return VisitResponse(
            id              = id,
            patientEhrId    = patient.ehrId,
            visitDate       = visitDate,
            createdAt       = createdAt,
            triageFiles     = triageFiles.toFileList(),
            reportFiles     = reportFiles.toFileList(),
            xrayFiles       = xrayFiles.toFileList(),
            xrayAnnotations = annotations,
        )
    }
}
