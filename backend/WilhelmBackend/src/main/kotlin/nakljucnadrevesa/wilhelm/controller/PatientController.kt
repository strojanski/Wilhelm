package nakljucnadrevesa.wilhelm.controller

import nakljucnadrevesa.wilhelm.dto.CreatePatientRequest
import nakljucnadrevesa.wilhelm.dto.PatientResponse
import nakljucnadrevesa.wilhelm.service.PatientService
import org.springframework.data.domain.Page
import org.springframework.data.domain.Pageable
import org.springframework.data.web.PageableDefault
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/patients")
class PatientController(private val patientService: PatientService) {

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun createPatient(@RequestBody request: CreatePatientRequest): PatientResponse =
        patientService.createPatient(request)

    @GetMapping
    fun getAllPatients(@PageableDefault(size = 20, sort = ["lastName"]) pageable: Pageable): Page<PatientResponse> =
        patientService.getAllPatients(pageable)

    @GetMapping("/{ehrId}")
    fun getPatient(@PathVariable ehrId: String): PatientResponse =
        patientService.getPatient(ehrId)

    @DeleteMapping("/{ehrId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun deletePatient(@PathVariable ehrId: String) =
        patientService.deletePatient(ehrId)
}
