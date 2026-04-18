package nakljucnadrevesa.wilhelm.dto

import nakljucnadrevesa.wilhelm.entity.Gender
import nakljucnadrevesa.wilhelm.entity.Patient

data class CreatePatientRequest(
    val firstName: String,
    val lastName: String,
    val ehrId: String,
    val age: Int,
    val gender: Gender
)

data class PatientResponse(
    val id: Long,
    val firstName: String,
    val lastName: String,
    val ehrId: String,
    val age: Int,
    val gender: Gender
)

fun Patient.toResponse() = PatientResponse(id, firstName, lastName, ehrId, age, gender)
