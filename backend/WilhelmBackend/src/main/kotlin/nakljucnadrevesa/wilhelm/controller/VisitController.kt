package nakljucnadrevesa.wilhelm.controller

import nakljucnadrevesa.wilhelm.dto.CreateVisitRequest
import nakljucnadrevesa.wilhelm.dto.SaveAnnotationsRequest
import nakljucnadrevesa.wilhelm.dto.VisitResponse
import nakljucnadrevesa.wilhelm.service.DocumentType
import nakljucnadrevesa.wilhelm.service.VisitService
import org.springframework.core.io.Resource
import org.springframework.format.annotation.DateTimeFormat
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpStatus
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile
import java.time.LocalDate

@RestController
@RequestMapping("/api/patients/{ehrId}/visits")
class VisitController(private val visitService: VisitService) {

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun createVisit(
        @PathVariable ehrId: String,
        @RequestBody request: CreateVisitRequest
    ): VisitResponse = visitService.createVisit(ehrId, request)

    @GetMapping
    fun getVisits(
        @PathVariable ehrId: String,
        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) date: LocalDate? = null
    ): List<VisitResponse> = visitService.getVisitsForPatient(ehrId, date)

    @GetMapping("/{visitId}")
    fun getVisit(@PathVariable visitId: Long): VisitResponse =
        visitService.getVisit(visitId)

    @DeleteMapping("/{visitId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun deleteVisit(@PathVariable visitId: Long) =
        visitService.deleteVisit(visitId)

    @PutMapping("/{visitId}/triage", consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
    fun uploadTriage(@PathVariable visitId: Long, @RequestParam("file") file: MultipartFile): VisitResponse =
        visitService.uploadDocument(visitId, DocumentType.TRIAGE, file)

    @GetMapping("/{visitId}/triage/{filename}")
    fun downloadTriage(@PathVariable visitId: Long, @PathVariable filename: String): ResponseEntity<Resource> =
        visitService.downloadDocument(visitId, DocumentType.TRIAGE, filename).asAttachment(filename, MediaType.APPLICATION_PDF)

    @PutMapping("/{visitId}/report", consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
    fun uploadReport(@PathVariable visitId: Long, @RequestParam("file") file: MultipartFile): VisitResponse =
        visitService.uploadDocument(visitId, DocumentType.REPORT, file)

    @GetMapping("/{visitId}/report/{filename}")
    fun downloadReport(@PathVariable visitId: Long, @PathVariable filename: String): ResponseEntity<Resource> =
        visitService.downloadDocument(visitId, DocumentType.REPORT, filename).asAttachment(filename, MediaType.APPLICATION_PDF)

    @PutMapping("/{visitId}/xray", consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
    fun uploadXray(@PathVariable visitId: Long, @RequestParam("file") file: MultipartFile): VisitResponse =
        visitService.uploadDocument(visitId, DocumentType.XRAY, file)

    @GetMapping("/{visitId}/xray/{filename}")
    fun downloadXray(@PathVariable visitId: Long, @PathVariable filename: String): ResponseEntity<Resource> =
        visitService.downloadDocument(visitId, DocumentType.XRAY, filename).asAttachment(filename, MediaType.IMAGE_PNG)

    @PostMapping("/{visitId}/xray/{filename}/analyze")
    fun analyzeXray(
        @PathVariable ehrId: String,
        @PathVariable visitId: Long,
        @PathVariable filename: String,
    ): VisitResponse = visitService.analyzeXray(ehrId, visitId, filename)

    @PutMapping("/{visitId}/xray/{filename}/annotations")
    fun saveAnnotations(
        @PathVariable visitId: Long,
        @PathVariable filename: String,
        @RequestBody req: SaveAnnotationsRequest,
    ): VisitResponse = visitService.saveAnnotations(visitId, filename, req)

    private fun Resource.asAttachment(filename: String, mediaType: MediaType): ResponseEntity<Resource> =
        ResponseEntity.ok()
            .contentType(mediaType)
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"$filename\"")
            .body(this)
}
