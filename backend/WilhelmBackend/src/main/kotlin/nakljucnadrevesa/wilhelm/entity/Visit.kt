package nakljucnadrevesa.wilhelm.entity

import jakarta.persistence.*
import java.time.Instant
import java.time.LocalDate

@Entity
@Table(name = "visits")
class Visit(

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    val id: Long = 0,

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id", nullable = false)
    val patient: Patient,

    @Column(name = "visit_date", nullable = false)
    val visitDate: LocalDate,

    @Column(name = "created_at", nullable = false, updatable = false)
    val createdAt: Instant = Instant.now(),

    @Column(name = "triage_files") var triageFiles: String = "",
    @Column(name = "report_files") var reportFiles: String = "",
    @Column(name = "xray_files")   var xrayFiles:   String = "",

    @Column(name = "xray_annotations", columnDefinition = "TEXT")
    var xrayAnnotations: String = "{}"
)
