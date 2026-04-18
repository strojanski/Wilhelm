package nakljucnadrevesa.wilhelm.entity

import jakarta.persistence.*

enum class Gender {
    MALE, FEMALE, OTHER
}

@Entity
@Table(name = "patients")
class Patient(

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    val id: Long = 0,

    @Column(name = "first_name", nullable = false)
    var firstName: String,

    @Column(name = "last_name", nullable = false)
    var lastName: String,

    @Column(name = "ehr_id", nullable = false, unique = true)
    var ehrId: String,

    @Column(nullable = false)
    var age: Int,

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    var gender: Gender,

    @OneToMany(mappedBy = "patient", cascade = [CascadeType.ALL], orphanRemoval = true)
    val visits: MutableList<Visit> = mutableListOf()
)
